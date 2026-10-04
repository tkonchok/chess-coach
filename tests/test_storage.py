from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
import sqlite3
import json
from tempfile import TemporaryDirectory
import unittest
from uuid import uuid4

from beta_fixtures import snapshot
from chess_coach.backup import restore
from chess_coach.storage import Conflict, Store


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)/'store.sqlite3'
        self.store = Store(self.path)
        self.uid,_ = self.store.login('test:a','a@example.invalid')
        self.other,_ = self.store.login('test:b','b@example.invalid')
        self.snapshot = snapshot()
        self.store.retain(self.uid,self.snapshot)

    def payload(self):
        return {'submission_id':str(uuid4()),'version_id':self.snapshot['version_id'],
                'proposed_move_uci':'e2e4','original_choice':'','original_reasoning':'',
                'dont_remember':False,'practice_reasoning':'','takeaway':'A useful note'}

    def test_restart_reopens_card_and_notes(self):
        value = self.payload()
        self.store.save_attempt(self.uid,value)
        restarted = Store(self.path)
        self.assertEqual(restarted.exercise(self.uid,value['version_id'])['card'],json.loads(json.dumps(self.snapshot['card'])))
        self.assertEqual(restarted.attempt(self.uid,value['submission_id'])['payload'],value)

    def test_import_capacity_is_atomic_and_existing_games_can_refresh(self):
        bundle={'games':[{'id':str(i)} for i in range(500)]}
        self.store.save_import(self.uid,bundle)
        self.store.add_game(self.uid,{'id':'0','updated':True})
        with self.assertRaises(Conflict):
            self.store.save_import(self.uid,{'games':[{'id':'overflow'}]})
        self.assertEqual(self.store.imported(self.uid),bundle)
        with self.assertRaises(KeyError):
            self.store.game(self.uid,'overflow')

    def test_same_submission_retry_and_concurrency(self):
        value = self.payload()
        with ThreadPoolExecutor(max_workers=2) as pool:
            timestamps = list(pool.map(lambda _:self.store.save_attempt(self.uid,value),range(2)))
        self.assertEqual(timestamps[0],timestamps[1])
        self.assertEqual(len(self.store.attempts(self.uid)),1)
        value['takeaway'] = 'changed'
        with self.assertRaises(Conflict):
            self.store.save_attempt(self.uid,value)

    def test_distinct_attempts_on_same_card_and_deletion_tombstone(self):
        first,second = self.payload(),self.payload()
        self.store.save_attempt(self.uid,first)
        self.store.save_attempt(self.uid,second)
        self.store.delete_attempt(self.uid,first['submission_id'])
        with self.assertRaises(Conflict):
            self.store.save_attempt(self.uid,first)
        self.assertEqual(len(self.store.attempts(self.uid)),1)
        self.store.exercise(self.uid,second['version_id'])

    def test_user_isolation(self):
        value = self.payload()
        self.store.save_attempt(self.uid,value)
        for read in (lambda:self.store.exercise(self.other,value['version_id']),
                     lambda:self.store.attempt(self.other,value['submission_id']),
                     lambda:self.store.delete_attempt(self.other,value['submission_id'])):
            with self.assertRaises(KeyError): read()
        self.assertEqual(self.store.attempts(self.other),[])

    def test_validation_unicode_and_illegal_move(self):
        value = self.payload()
        value['takeaway'] = '♟' * 2000
        self.store.save_attempt(self.uid,value)
        for updates in ({'takeaway':'x'*2001},{'dont_remember':1},{'proposed_move_uci':'e2e5'},
                        {'submission_id':'bad'},{'original_choice':'diagnosed'}):
            with self.subTest(updates=updates):
                value = self.payload() | updates
                with self.assertRaises(ValueError):self.store.save_attempt(self.uid,value)

    def test_backup_restores_to_separate_store(self):
        value = self.payload()
        self.store.save_attempt(self.uid,value)
        backup = Path(self.directory.name)/'backup.sqlite3'
        destination = Path(self.directory.name)/'restored.sqlite3'
        self.store.backup(backup)
        restore(backup,destination)
        self.assertEqual(Store(destination).attempt(self.uid,value['submission_id'])['payload'],value)
        with self.assertRaises(ValueError):restore(backup,destination)

    def test_unknown_or_unversioned_schema_refused(self):
        with self.store.connect() as db:db.execute('PRAGMA user_version=9')
        with self.assertRaises(ValueError):Store(self.path)
        extra = Path(self.directory.name)/'unknown.sqlite3'
        with closing(sqlite3.connect(extra)) as db:
            db.execute('CREATE TABLE unknown (id INTEGER)');db.commit()
        with self.assertRaises(ValueError):Store(extra)

    def test_sessions_logout_and_expiration(self):
        uid,token = self.store.login('test:a','new@example.invalid')
        self.assertEqual(uid,self.uid)
        self.assertEqual(self.store.user(token),uid)
        self.store.logout(token)
        self.assertIsNone(self.store.user(token))

    def test_queue_limits_and_restart_recovery(self):
        jobs = []
        for index in range(4):
            uid,_=self.store.login('queue:'+str(index),'test@example.invalid')
            self.store.add_game(uid,{'id':'g','pgn':'*','color':'white'})
            if index == 3:
                with self.assertRaises(Conflict):self.store.enqueue(uid,'g')
            else:jobs.append((uid,self.store.enqueue(uid,'g')))
        running = self.store.claim()
        self.assertIsNone(self.store.claim())
        with self.assertRaises(Conflict):self.store.enqueue(jobs[0][0],'g')
        self.store.recover()
        self.assertEqual(self.store.job(running['user_id'],running['id'])['status'],'failed')
        self.assertIsNotNone(self.store.claim())

    def test_daily_quota_transaction_rolls_back(self):
        self.store.add_game(self.uid,{'id':'g'})
        job=self.store.enqueue(self.uid,'g')
        self.store.fail(job,'test')
        with self.assertRaises(Conflict):self.store.enqueue(self.uid,'g')
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT count FROM usage WHERE kind='analysis' AND user_id=?",(self.uid,)).fetchone()[0],1)

    def test_failed_completion_rolls_back_retention_and_status(self):
        self.store.add_game(self.uid,{'id':'g'})
        jobid=self.store.enqueue(self.uid,'g');job=self.store.claim()
        changed=snapshot(); changed['card']['explanation']='tampered'
        with self.assertRaises(ValueError):self.store.complete(job,{'exercises':[changed]})
        self.assertEqual(self.store.job(self.uid,jobid)['status'],'running')
