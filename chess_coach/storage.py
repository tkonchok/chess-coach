"""Versioned SQLite operations; user scope is explicit on every personal lookup."""

from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path
import secrets
import sqlite3
import time
from uuid import UUID, uuid4

import chess

from chess_coach.exercises import card_from_exercise

CHOICES = {'missed_threat', 'miscalculated', 'other_idea', 'time_pressure', 'misclick', 'dont_remember'}


def encode(value):
    return json.dumps(value, sort_keys=True, allow_nan=False)


class Conflict(ValueError):
    pass


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version == 0:
                if db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone():
                    raise ValueError('Refusing unversioned nonempty database')
                statements = [
                    'CREATE TABLE users (id TEXT PRIMARY KEY, subject TEXT UNIQUE NOT NULL, email TEXT NOT NULL)',
                    'CREATE TABLE sessions (token TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), expires REAL NOT NULL)',
                    'CREATE TABLE games (user_id TEXT NOT NULL REFERENCES users(id), id TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY(user_id,id))',
                    'CREATE TABLE imports (user_id TEXT PRIMARY KEY REFERENCES users(id), data TEXT NOT NULL)',
                    'CREATE TABLE jobs (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), game_id TEXT NOT NULL, status TEXT NOT NULL, created REAL NOT NULL, result TEXT, error TEXT)',
                    'CREATE TABLE exercises (user_id TEXT NOT NULL REFERENCES users(id), version TEXT NOT NULL, snapshot TEXT NOT NULL, PRIMARY KEY(user_id,version))',
                    'CREATE TABLE attempts (user_id TEXT NOT NULL REFERENCES users(id), submission TEXT NOT NULL, version TEXT NOT NULL, payload TEXT, completed REAL NOT NULL, deleted INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(user_id,submission), FOREIGN KEY(user_id,version) REFERENCES exercises(user_id,version))',
                    'CREATE TABLE usage (user_id TEXT NOT NULL, day TEXT NOT NULL, kind TEXT NOT NULL, count INTEGER NOT NULL, PRIMARY KEY(user_id,day,kind))',
                    'CREATE TABLE explanations (key TEXT PRIMARY KEY, data TEXT NOT NULL)',
                ]
                for sql in statements:
                    db.execute(sql)
                db.execute('PRAGMA user_version=1')
            elif version != 1:
                raise ValueError('Unsupported database version; migration required')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def login(self, subject, email):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT INTO users VALUES(?,?,?) ON CONFLICT(subject) DO UPDATE SET email=excluded.email',
                       (str(uuid4()), subject, email))
            uid = db.execute('SELECT id FROM users WHERE subject=?', (subject,)).fetchone()['id']
            token = secrets.token_urlsafe(32)
            db.execute('DELETE FROM sessions WHERE expires < ?', (time.time(),))
            db.execute('INSERT INTO sessions VALUES(?,?,?)',
                       (sha256(token.encode()).hexdigest(), uid, time.time() + 7 * 86400))
            return uid, token

    def user(self, token):
        if not token:
            return None
        with self.connect() as db:
            row = db.execute('SELECT user_id FROM sessions WHERE token=? AND expires>?',
                             (sha256(token.encode()).hexdigest(), time.time())).fetchone()
            return row['user_id'] if row else None

    def logout(self, token):
        with self.connect() as db:
            db.execute('DELETE FROM sessions WHERE token=?', (sha256(token.encode()).hexdigest(),))

    def add_game(self, uid, game):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self._check_game_capacity(db, uid, [game['id']])
            db.execute('INSERT INTO games VALUES(?,?,?) ON CONFLICT(user_id,id) DO UPDATE SET data=excluded.data',
                       (uid, game['id'], encode(game)))

    def _check_game_capacity(self, db, uid, incoming):
        existing = {row[0] for row in db.execute('SELECT id FROM games WHERE user_id=?', (uid,))}
        if len(existing | set(incoming)) > 500:
            raise Conflict('This beta stores up to 500 imported games per account')

    def save_import(self, uid, bundle, *, persist_games=True):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self._check_game_capacity(db, uid, [game['id'] for game in bundle['games']] if persist_games else [])
            db.execute('INSERT INTO imports VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET data=excluded.data', (uid, encode(bundle)))
            for game in bundle['games'] if persist_games else []:
                db.execute('INSERT INTO games VALUES(?,?,?) ON CONFLICT(user_id,id) DO UPDATE SET data=excluded.data', (uid, game['id'], encode(game)))

    def imported(self, uid):
        with self.connect() as db:
            row = db.execute('SELECT data FROM imports WHERE user_id=?', (uid,)).fetchone()
            return json.loads(row[0]) if row else None

    def game(self, uid, gid):
        with self.connect() as db:
            row = db.execute('SELECT data FROM games WHERE user_id=? AND id=?', (uid, gid)).fetchone()
            if row is not None:
                return json.loads(row[0])
            # A browsed page is owned transient source data, not a durable game.
            imported = db.execute('SELECT data FROM imports WHERE user_id=?', (uid,)).fetchone()
            if imported:
                for game in json.loads(imported[0]).get('games',[]):
                    if game['id'] == gid:
                        return game
            raise KeyError('Game not found')

    def _quota(self, db, uid, kind, user_limit, global_limit):
        day = time.strftime('%Y-%m-%d', time.gmtime())
        own = db.execute('SELECT count FROM usage WHERE user_id=? AND day=? AND kind=?', (uid, day, kind)).fetchone()
        total = db.execute('SELECT COALESCE(SUM(count),0) FROM usage WHERE day=? AND kind=?', (day, kind)).fetchone()[0]
        if (own and own[0] >= user_limit) or total >= global_limit:
            action = {'analysis':'game analysis', 'import':'game import', 'ai':'AI coaching', 'exploration':'position analysis'}.get(kind, kind)
            scope = f'{user_limit} per account' if own and own[0] >= user_limit else f'{global_limit} across this installation'
            raise Conflict(f'Daily {action} allowance reached ({scope}). It resets at 00:00 UTC. Saved practice remains available.')
        db.execute('INSERT INTO usage VALUES(?,?,?,1) ON CONFLICT(user_id,day,kind) DO UPDATE SET count=count+1', (uid, day, kind))

    def reserve_ai(self, uid):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self._quota(db, uid, 'ai', 5, 100)

    def reserve_exploration(self, uid, *, local=False):
        if local:
            return  # Localhost-only testing: no daily exploration cap.
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self._quota(db, uid, 'exploration', 100, 300)

    def enqueue(self, uid, gid, *, daily_limit=1):
        if type(daily_limit) is not int or not 1 <= daily_limit <= 20:
            raise ValueError('Analysis daily limit must be between 1 and 20')
        self.game(uid, gid)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute("SELECT id FROM jobs WHERE user_id=? AND status IN ('queued','running')", (uid,)).fetchone():
                raise Conflict('You already have an active analysis')
            if db.execute("SELECT COUNT(*) FROM jobs WHERE status='queued'").fetchone()[0] >= 3:
                raise Conflict('Analysis queue is full; try later')
            self._quota(db, uid, 'analysis', daily_limit, 30)
            jid = str(uuid4())
            db.execute("INSERT INTO jobs VALUES(?,?,?,'queued',?,NULL,NULL)", (jid, uid, gid, time.time()))
            return jid

    def claim(self):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute("SELECT id FROM jobs WHERE status='running'").fetchone():
                return None
            row = db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
            if row:
                db.execute("UPDATE jobs SET status='running' WHERE id=?", (row['id'],))
                return dict(row)

    def recover(self):
        with self.connect() as db:
            db.execute("UPDATE jobs SET status='failed',error='Analysis interrupted by restart; no partial result saved' WHERE status='running'")

    def complete(self, job, result):
        for item in result['exercises']:
            card_from_exercise(item)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for item in result['exercises']:
                self._exercise(db, job['user_id'], item)
            db.execute("UPDATE jobs SET status='completed',result=?,error=NULL WHERE id=? AND status='running'", (encode(result), job['id']))

    def fail(self, jid, error):
        with self.connect() as db:
            db.execute("UPDATE jobs SET status='failed',error=? WHERE id=? AND status IN ('running','queued')", (error, jid))

    def job(self, uid, jid):
        with self.connect() as db:
            row = db.execute('SELECT * FROM jobs WHERE user_id=? AND id=?', (uid, jid)).fetchone()
            if row is None:
                raise KeyError('Analysis not found')
            result = dict(row)
            result['result'] = json.loads(result['result']) if result['result'] else None
            return result

    def completed_game_jobs(self, uid):
        with self.connect() as db:
            rows = db.execute("SELECT game_id,id FROM jobs WHERE user_id=? AND status='completed' ORDER BY created DESC", (uid,)).fetchall()
            result = {}
            for row in rows:
                result.setdefault(row['game_id'], row['id'])
            return result

    def jobs(self, uid):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT id,status,created,error FROM jobs WHERE user_id=? ORDER BY created DESC LIMIT 30', (uid,))]

    def _exercise(self, db, uid, snapshot):
        version, content = snapshot['version_id'], encode(snapshot)
        row = db.execute('SELECT snapshot FROM exercises WHERE user_id=? AND version=?', (uid, version)).fetchone()
        if row and row[0] != content:
            raise Conflict('Existing exercise version changed')
        db.execute('INSERT OR IGNORE INTO exercises VALUES(?,?,?)', (uid, version, content))

    def retain(self, uid, snapshot):
        card_from_exercise(snapshot)
        with self.connect() as db:
            self._exercise(db, uid, snapshot)

    def practice_library(self, uid):
        """Retained positions with completion counts; notes remain in owned attempts."""
        with self.connect() as db:
            rows = db.execute('SELECT e.version,e.snapshot,COUNT(a.submission) AS completed FROM exercises e LEFT JOIN attempts a ON a.user_id=e.user_id AND a.version=e.version AND a.deleted=0 WHERE e.user_id=? GROUP BY e.version,e.snapshot ORDER BY e.rowid DESC', (uid,)).fetchall()
            return [dict(version=row['version'], exercise=json.loads(row['snapshot']), completed=row['completed']) for row in rows]

    def exercise(self, uid, version):
        with self.connect() as db:
            row = db.execute('SELECT snapshot FROM exercises WHERE user_id=? AND version=?', (uid, version)).fetchone()
            if row is None:
                raise KeyError('Exercise not found')
            value = json.loads(row[0])
        card_from_exercise(value)
        return value

    def save_attempt(self, uid, value):
        required = {'submission_id','version_id','proposed_move_uci','original_choice', 'original_reasoning','dont_remember','practice_reasoning','takeaway'}
        if not isinstance(value, dict) or set(value) != required:
            raise ValueError('Unexpected attempt fields')
        try:
            UUID(value['submission_id'])
        except (ValueError, TypeError, AttributeError) as error:
            raise ValueError('Invalid submission ID') from error
        if (type(value['dont_remember']) is not bool or not isinstance(value['original_choice'], str)
                or value['original_choice'] not in CHOICES | {''}):
            raise ValueError('Invalid reflection choice')
        for field in ('original_reasoning','practice_reasoning','takeaway'):
            if not isinstance(value[field], str) or len(value[field]) > 2000:
                raise ValueError('Notes must be strings of at most 2000 characters')
        card = card_from_exercise(self.exercise(uid, value['version_id']))
        try:
            board = chess.Board(card.position_fen)
            move = chess.Move.from_uci(value['proposed_move_uci'])
            if move not in board.legal_moves:
                raise ValueError('Illegal proposed move')
        except (ValueError, TypeError) as error:
            raise ValueError('Invalid proposed move') from error
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            previous = db.execute('SELECT * FROM attempts WHERE user_id=? AND submission=?', (uid,value['submission_id'])).fetchone()
            if previous:
                if previous['deleted'] or previous['payload'] != encode(value):
                    raise Conflict('Submission already used or deleted; start a new attempt')
                return previous['completed']
            completed = time.time()
            db.execute('INSERT INTO attempts VALUES(?,?,?,?,?,0)', (uid,value['submission_id'],value['version_id'],encode(value),completed))
            return completed

    def attempts(self, uid):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT submission,version,completed FROM attempts WHERE user_id=? AND deleted=0 ORDER BY completed DESC', (uid,))]

    def reflections(self, uid):
        with self.connect() as db:
            rows = db.execute('SELECT submission,version,completed,payload FROM attempts WHERE user_id=? AND deleted=0 ORDER BY completed DESC',(uid,)).fetchall()
            result = []
            for row in rows:
                payload = json.loads(row['payload'])
                if any(payload.get(field) for field in ('original_choice','original_reasoning','practice_reasoning','takeaway','dont_remember')):
                    result.append(dict(submission=row['submission'],version=row['version'],completed=row['completed']))
            return result

    def attempt(self, uid, submission):
        with self.connect() as db:
            row = db.execute('SELECT * FROM attempts WHERE user_id=? AND submission=? AND deleted=0', (uid,submission)).fetchone()
            if row is None:
                raise KeyError('Attempt not found')
            value = dict(row)
            value['payload'] = json.loads(value['payload'])
            return value

    def delete_attempt(self, uid, submission):
        self.attempt(uid, submission)
        with self.connect() as db:
            # Tombstone prevents a delayed save retry resurrecting deleted notes.
            db.execute('UPDATE attempts SET deleted=1,payload=NULL WHERE user_id=? AND submission=?', (uid,submission))

    def cache(self, key, value=None):
        with self.connect() as db:
            if value is not None:
                db.execute('INSERT OR IGNORE INTO explanations VALUES(?,?)', (key, encode(value)))
            row = db.execute('SELECT data FROM explanations WHERE key=?', (key,)).fetchone()
            return json.loads(row[0]) if row else None

    def backup(self, destination):
        if Path(destination).exists():
            raise ValueError('Backup destination must be new')
        with self.connect() as source:
            target = sqlite3.connect(destination)
            try:
                source.backup(target)
                if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise RuntimeError('Backup integrity check failed')
            finally:
                target.close()
