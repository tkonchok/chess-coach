from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import chess
from unittest.mock import Mock, patch
from uuid import uuid4

from beta_fixtures import snapshot
from chess_coach.beta import create_app
from chess_coach.storage import Conflict
from test_walkthrough import prepared, commentary


class BetaTests(unittest.TestCase):
    def test_public_health_accepts_railway_probe_but_rejects_unknown_host(self):
        with TemporaryDirectory() as directory:
            app=create_app({'SECRET_KEY':'x'*64,'APP_ORIGIN':'https://coach.example',
                'DATABASE':str(Path(directory)/'health.sqlite3'),'START_SUPERVISOR':False,
                'LOCAL_DEMO':False,'LOCAL_TESTING':False})
            client=app.test_client()
            self.assertEqual(client.get('/health',base_url='https://healthcheck.railway.app').status_code,200)
            self.assertEqual(client.get('/health',base_url='https://untrusted.example').status_code,400)

    def test_owned_thumbnails_render_without_inline_styles_and_recheck_ownership(self):
        from xml.etree import ElementTree
        self.store.add_game(self.uid,{'id':'thumb','pgn':self.snapshot['source']['pgn'],'color':'white'})
        for path in ('/games/thumb/thumbnail.svg',self.base+'/thumbnail.svg'):
            response=self.client.get(path)
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.mimetype,'image/svg+xml')
            root=ElementTree.fromstring(response.data)
            self.assertFalse(any('style' in element.attrib for element in root.iter()))
            ids={element.attrib['id'] for element in root.iter() if 'id' in element.attrib}
            for element in root.iter():
                href=element.attrib.get('{http://www.w3.org/1999/xlink}href')
                if href:self.assertIn(href.removeprefix('#'),ids)
            self.assertEqual(self.client.get(path,headers={'If-None-Match':response.headers['ETag']}).status_code,304)
            other=self.app.test_client();other.get('/');_,token=self.store.login('thumb-other','other@example.invalid')
            with other.session_transaction() as session:session['login_token']=token
            self.assertEqual(other.get(path,headers={'If-None-Match':response.headers['ETag']}).status_code,404)
    def test_puzzle_library_is_owned_and_tracks_saved_attempts(self):
        response=self.client.get('/puzzles')
        self.assertEqual(response.status_code,200)
        self.assertIn(b'Not yet practiced',response.data)
        self.post(self.base+'/api/attempts',json=self.payload())
        self.assertIn(b'Practiced',self.client.get('/puzzles').data)
        self.assertEqual(self.store.practice_library(self.uid)[0]['completed'],1)
        other=self.app.test_client();other.get('/');uid,token=self.store.login('library-other','other@example.invalid')
        with other.session_transaction() as session:session['login_token']=token
        self.assertEqual(self.store.practice_library(uid),[])
        self.assertNotIn(self.snapshot['version_id'].encode(),other.get('/puzzles').data)

    def test_completed_analysis_opens_existing_job_without_new_quota(self):
        self.store.add_game(self.uid,{'id':'already','pgn':self.snapshot['source']['pgn'],'color':'white'})
        jid=self.store.enqueue(self.uid,'already',daily_limit=20)
        job=self.store.claim();self.store.complete(job,{'exercises':[self.snapshot],'report':{}})
        with patch.object(self.store,'enqueue',side_effect=AssertionError('must reuse completed work')):
            response=self.post('/analyze/already')
        self.assertEqual(response.status_code,302)
        self.assertTrue(response.location.endswith('/jobs/'+jid))

    def test_local_exploration_has_no_daily_cap_but_public_cap_remains(self):
        with self.store.connect() as db:
            for _ in range(500): self.store._quota(db,self.uid,'exploration',500,1000)
        self.store.reserve_exploration(self.uid,local=True)
        with self.assertRaises(Conflict):
            self.store.reserve_exploration(self.uid,local=False)

    def test_library_filters_repeat_saves_and_deletion_progress(self):
        first=self.payload();second=self.payload()
        for value in (first,second): self.post(self.base+'/api/attempts',json=value)
        page=self.client.get('/puzzles?status=practiced').get_data(as_text=True)
        self.assertIn('1 of 1 practiced',page)
        self.assertIn('All caught up.',self.client.get('/puzzles?status=remaining').get_data(as_text=True))
        self.store.delete_attempt(self.uid,first['submission_id'])
        self.assertIn('1 of 1 practiced',self.client.get('/puzzles').get_data(as_text=True))
        self.store.delete_attempt(self.uid,second['submission_id'])
        self.assertIn('No practiced positions yet.',self.client.get('/puzzles?status=practiced').get_data(as_text=True))
        self.assertIn('Not yet practiced',self.client.get('/puzzles?status=unknown').get_data(as_text=True))

    def test_analysis_states_and_missing_game_fallback(self):
        self.store.add_game(self.uid,{'id':'screen','pgn':self.snapshot['source']['pgn'],'color':'white'})
        jid=self.store.enqueue(self.uid,'screen',daily_limit=20)
        self.assertIn(b'Queued',self.client.get('/jobs/'+jid).data)
        other=self.app.test_client();other.get('/');_,token=self.store.login('job-other','job@example.invalid')
        with other.session_transaction() as session: session['login_token']=token
        self.assertEqual(other.get('/jobs/'+jid).status_code,404)
        job=self.store.claim()
        self.assertIn(b'Analyzing',self.client.get('/jobs/'+jid).data)
        self.store.complete(job,{'exercises':[self.snapshot],'report':{}})
        ready=self.client.get('/jobs/'+jid).get_data(as_text=True)
        self.assertIn('position-card',ready);self.assertNotIn('Practice next position',ready);self.assertIn('Opponent',ready)
        self.post(self.base+'/api/attempts',json=self.payload())
        self.assertIn(b'Practiced',self.client.get('/jobs/'+jid).data)
        with self.store.connect() as db: db.execute('DELETE FROM games WHERE user_id=? AND id=?',(self.uid,'screen'))
        self.assertIn(b'Opponent',self.client.get('/jobs/'+jid).data)
        with self.store.connect() as db:
            db.execute("UPDATE jobs SET result=? WHERE id=?", ('{"exercises":[],"report":{}}',jid))
        self.assertIn(b'No suitable positions',self.client.get('/jobs/'+jid).data)
        with self.store.connect() as db: db.execute("UPDATE jobs SET status='running' WHERE id=?",(jid,))
        self.store.fail(jid,'Engine timeout fixture')
        self.assertIn(b'Engine timeout fixture',self.client.get('/jobs/'+jid).data)

    def test_signed_out_landing_explains_preview_and_login_availability(self):
        page=self.app.test_client().get('/').get_data(as_text=True)
        self.assertIn('Turn your own games into better practice.',page)
        self.assertIn('Illustrative preview',page)
        self.assertIn('Google sign-in is not configured',page)
        self.assertNotIn('Continue with Google',page)

    def test_reflections_omit_blank_attempts_and_scope_notes(self):
        blank=self.payload()
        for key in ('original_choice','original_reasoning','practice_reasoning','takeaway'): blank[key]=''
        self.store.save_attempt(self.uid,blank)
        self.assertIn(b'Keep an idea when it matters.',self.client.get('/reflections').data)
        note=self.payload();self.store.save_attempt(self.uid,note)
        self.assertEqual(len(self.store.reflections(self.uid)),1)
        self.assertIn(note['submission_id'].encode(),self.client.get('/reflections').data)
        self.assertNotIn(note['submission_id'].encode(),self.client.get('/puzzles').data)
        self.store.delete_attempt(self.uid,note['submission_id'])
        self.assertEqual(self.store.reflections(self.uid),[])

    def test_castling_original_move_is_explained_and_numbered(self):
        from chess_coach.training import TrainingCard
        for san,label in [('O-O','kingside castling'),('O-O-O','queenside castling')]:
            card=TrainingCard(20,'r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 11',san,'Choose a move.',(san,),'Fixture.')
            with patch('chess_coach.beta.card_from_exercise',return_value=card):
                page=self.client.get(self.base).get_data(as_text=True)
            self.assertIn('move 11:',page)
            self.assertIn(label,page)

    def prepare_walk(self):
        state=self.client.get(self.base+'/api/position').get_json()
        evidence=prepared()
        def run(fen,proposed,recommended,reserve):
            reserve();return evidence
        supervisor=Mock();supervisor.walkthrough.side_effect=run
        self.app.extensions['supervisor']=supervisor
        data={'card_id':state['card_id'],'proposed_move_uci':'e2e4'}
        response=self.post(self.base+'/api/walkthrough',json=data)
        self.assertEqual(response.status_code,200)
        return evidence,data,supervisor

    def test_walkthrough_scope_inputs_cache_and_commentary(self):
        evidence,data,supervisor=self.prepare_walk()
        self.post(self.base+'/api/walkthrough',json=data)
        supervisor.walkthrough.assert_called_once()
        for invalid in (data | {'fen':'arbitrary'},data | {'proposed_move_uci':'e2e5'}):
            self.assertEqual(self.post(self.base+'/api/walkthrough',json=invalid).status_code,400)
        self.assertEqual(self.client.post(self.base+'/api/walkthrough',json=data).status_code,403)
        other=self.app.test_client();other.get('/');_,token=self.store.login('walk-other','other@example.invalid')
        with other.session_transaction() as session:session['login_token']=token
        self.assertEqual(self.post(self.base+'/api/walkthrough',client=other,json=data).status_code,404)
        payload=data | {'walkthrough_id':evidence['walkthrough_id'],'consent':True}
        self.assertEqual(self.post(self.base+'/api/walkthrough/commentary',client=other,json=payload).status_code,404)
        self.assertEqual(self.post(self.base+'/api/walkthrough/commentary',json=payload | {'walkthrough_id':'wrong'}).status_code,409)
        self.assertEqual(self.post(self.base+'/api/walkthrough/commentary',json=payload | {'consent':False}).status_code,400)
        self.app.config.update(WALKTHROUGH_AI_ENABLED=True,GROQ_API_KEY='configured')
        with patch('chess_coach.beta.coach_walkthrough',return_value=commentary(evidence)) as provider:
            result=self.post(self.base+'/api/walkthrough/commentary',json=payload).get_json()
            self.assertTrue(result['available']);self.assertEqual(result['walkthrough_id'],evidence['walkthrough_id'])
            self.assertTrue(self.post(self.base+'/api/walkthrough/commentary',json=payload).get_json()['available'])
            provider.assert_called_once()

    def test_walkthrough_failure_fallback_and_public_quality_gate(self):
        evidence,data,_=self.prepare_walk()
        payload=data | {'walkthrough_id':evidence['walkthrough_id'],'consent':True}
        self.app.config.update(WALKTHROUGH_AI_ENABLED=False,LOCAL_TESTING=False,GROQ_API_KEY='configured')
        self.assertEqual(self.post(self.base+'/api/walkthrough/commentary',json=payload).get_json()['reason'],'quality_gate')
        self.app.config['WALKTHROUGH_AI_ENABLED']=True
        for error,reason in [(TimeoutError(),'connection'),(ValueError(),'invalid_response'),(Conflict('quota'),'quota')]:
            with patch('chess_coach.beta.coach_walkthrough',side_effect=error):
                result=self.post(self.base+'/api/walkthrough/commentary',json=payload).get_json()
                self.assertFalse(result['available']);self.assertEqual(result['reason'],reason)
        self.app.config['GROQ_API_KEY']=''
        self.assertEqual(self.post(self.base+'/api/walkthrough/commentary',json=payload).get_json()['reason'],'configuration')

    def setUp(self):
        self.directory=TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.app=create_app({'TESTING':True,'SECRET_KEY':'test-secret','DATABASE':str(Path(self.directory.name)/'db'),
                             'LOCAL_DEMO':True,'START_SUPERVISOR':False,'AUTOMATIC_EXERCISES_ENABLED':True})
        self.store=self.app.extensions['store']
        self.client=self.app.test_client()
        self.client.get('/')
        self.client.post('/local-login',data={'csrf':self.csrf()})
        with self.client.session_transaction() as session:self.uid=self.store.user(session['login_token'])
        self.snapshot=snapshot();self.store.retain(self.uid,self.snapshot)
        self.base='/practice/'+self.snapshot['version_id']

    def csrf(self,client=None):
        with (client or self.client).session_transaction() as session:return session['csrf']

    def post(self,path,*,client=None,**kwargs):
        client=client or self.client
        return client.post(path,headers={'X-CSRF-Token':self.csrf(client)},**kwargs)

    def payload(self):
        return {'submission_id':str(uuid4()),'version_id':self.snapshot['version_id'],'proposed_move_uci':'e2e4',
                'original_choice':'miscalculated','original_reasoning':'<script>never execute</script>',
                'dont_remember':False,'practice_reasoning':'new attempt','takeaway':'♟'*2000}

    def test_practice_and_save_with_unicode_history_and_escaping(self):
        self.assertEqual(self.client.get(self.base).status_code,200)
        state=self.client.get(self.base+'/api/position').get_json()
        response=self.post(self.base+'/api/position',json={'card_id':state['card_id'],'moves':['e2e4']})
        self.assertEqual(response.get_json()['sans'],['e4'])
        self.assertEqual(self.client.get(self.base+'/api/reveal').status_code,200)
        payload=self.payload()
        saved=self.post(self.base+'/api/attempts',json=payload)
        self.assertEqual(saved.status_code,200)
        self.assertEqual(self.post(self.base+'/api/attempts',json=payload).status_code,200)
        detail=self.client.get(saved.get_json()['url']).get_data(as_text=True)
        self.assertIn('&lt;script&gt;',detail)
        self.assertNotIn('<script>never execute</script>',detail)
        self.assertIn('♟'*2000,detail)
        self.assertEqual(len(self.store.attempts(self.uid)),1)

    def test_other_account_cannot_read_save_or_delete_personal_resources(self):
        other=self.app.test_client();other.get('/')
        _,token=self.store.login('other','other@example.invalid')
        with other.session_transaction() as session:session['login_token']=token
        payload=self.payload();self.store.save_attempt(self.uid,payload)
        self.store.add_game(self.uid,{'id':'owned'})
        jid=self.store.enqueue(self.uid,'owned')
        for path in (self.base,self.base+'/api/position',self.base+'/api/reveal','/history/'+payload['submission_id']):
            self.assertEqual(other.get(path).status_code,404)
        self.assertEqual(self.post(self.base+'/api/attempts',client=other,json=payload).status_code,404)
        self.assertEqual(self.post(self.base+'/api/engine',client=other,json={'card_id':'private-card','moves':[]}).status_code,404)
        self.assertEqual(self.post('/history/'+payload['submission_id']+'/delete',client=other,data={'confirm':'yes'}).status_code,404)
        self.assertEqual(self.post('/analyze/owned',client=other).status_code,404)
        self.assertEqual(other.get('/jobs/'+jid).status_code,404)
        self.assertEqual(other.get('/api/jobs/'+jid).status_code,404)

    def test_csrf_foreign_origin_and_host(self):
        self.assertEqual(self.client.post(self.base+'/api/attempts',json=self.payload()).status_code,403)
        self.assertEqual(self.client.post('/logout',headers={'X-CSRF-Token':self.csrf(),'Origin':'https://evil.example'}).status_code,403)
        self.assertEqual(self.client.get('/',headers={'Host':'evil.example'}).status_code,400)

    def test_anonymous_api_requires_signin(self):
        self.assertEqual(self.app.test_client().get(self.base+'/api/position').status_code,401)

    def test_exploration_engine_replays_owned_card_and_rejects_arbitrary_positions(self):
        state=self.client.get(self.base+'/api/position').get_json()
        supervisor=Mock()
        board=chess.Board();board.push_uci('e2e4')
        supervisor.explore.return_value={'fen':board.fen(),'centipawns':25,'mate':None,
                                       'best_move_uci':'e7e5','best_move_san':'e5','line':['e5'],'terminal':None,'depth':12}
        self.app.extensions['supervisor']=supervisor
        result=self.post(self.base+'/api/engine',json={'card_id':state['card_id'],'moves':['e2e4']})
        self.assertEqual(result.status_code,200)
        self.assertEqual(supervisor.explore.call_args.args[0],board.fen())
        self.assertEqual(result.get_json()['centipawns'],25)
        for value in ({'card_id':state['card_id'],'moves':['e2e5']},
                      {'card_id':state['card_id'],'moves':[],'fen':board.fen()}):
            self.assertEqual(self.post(self.base+'/api/engine',json=value).status_code,400)
        supervisor.explore.side_effect=RuntimeError('Engine is busy')
        self.assertEqual(self.post(self.base+'/api/engine',json={'card_id':state['card_id'],'moves':[]}).status_code,503)

    def test_coaching_disabled_invalid_timeout_and_quota_fallback(self):
        for key in ('', 'configured'):
            self.app.config['GROQ_API_KEY']=key
            with patch('chess_coach.beta.coach',side_effect=TimeoutError):
                response=self.post(self.base+'/api/coaching',json={'consent':True})
                self.assertEqual(response.status_code,200)
                self.assertFalse(response.get_json()['available'])
        self.assertEqual(self.post(self.base+'/api/coaching',json={'consent':False}).status_code,400)

    def test_coaching_cache_excludes_attempts_and_identity(self):
        self.app.config['GROQ_API_KEY']='test'
        answer={'explanation':'Consider d4.', 'suggestion':'Check the reply.', 'move_references':['d4']}
        with patch('chess_coach.beta.coach',return_value=answer) as provider:
            self.assertTrue(self.post(self.base+'/api/coaching',json={'consent':True}).get_json()['available'])
            self.assertTrue(self.post(self.base+'/api/coaching',json={'consent':True}).get_json()['available'])
            provider.assert_called_once()
            self.assertEqual(len(provider.call_args.args),3)

    def test_exhausted_ai_quota_preserves_engine_practice_and_save(self):
        self.app.config['GROQ_API_KEY']='test'
        for _ in range(5):self.store.reserve_ai(self.uid)
        with patch('chess_coach.beta.coach') as provider:
            result=self.post(self.base+'/api/coaching',json={'consent':True}).get_json()
            self.assertFalse(result['available'])
            self.assertEqual(result['reason'],'quota')
            provider.assert_not_called()
        self.assertEqual(self.client.get(self.base+'/api/reveal').status_code,200)
        self.assertEqual(self.post(self.base+'/api/attempts',json=self.payload()).status_code,200)

    def test_coaching_errors_are_specific_and_do_not_expose_provider_details(self):
        from urllib.error import HTTPError
        self.app.config['GROQ_API_KEY']='test'
        errors=[(HTTPError('https://provider.invalid',401,'secret-provider-message',{},None),'credentials'),
                (HTTPError('https://provider.invalid',403,'secret-provider-message',{},None),'provider_rejected'),
                (HTTPError('https://provider.invalid',429,'secret-provider-message',{},None),'provider_quota'),
                (TimeoutError(),'timeout'),(ValueError('secret-provider-message'),'invalid_response')]
        for error,reason in errors:
            with patch('chess_coach.beta.coach',side_effect=error):
                result=self.post(self.base+'/api/coaching',json={'consent':True}).get_json()
            self.assertEqual(result['reason'],reason)
            self.assertNotIn('secret-provider-message',str(result))

    def test_delete_requires_confirmation_and_never_resurrects(self):
        payload=self.payload();self.store.save_attempt(self.uid,payload)
        path='/history/'+payload['submission_id']+'/delete'
        self.assertEqual(self.post(path,data={}).status_code,400)
        self.assertEqual(self.post(path,data={'confirm':'yes'}).status_code,302)
        self.assertEqual(self.post(self.base+'/api/attempts',json=payload).status_code,409)
        self.assertEqual(self.client.get('/history/'+payload['submission_id']).status_code,404)

    def test_archive_owned_transient_page_and_selected_game_survives_navigation(self):
        from test_chesscom import archived_game, BASE
        from chess_coach.chesscom import browse_archive
        remote=Mock();remote.observations=[]
        remote.get.side_effect=lambda url,**kw: {'archives':[BASE+'/games/2026/09']} if url.endswith('/archives') else {'games':[archived_game(1)]}
        bundle=browse_archive(remote,'learner')
        with patch('chess_coach.beta.browse_archive',return_value=bundle):
            response=self.client.get('/archive?username=learner&month=2026-09')
        self.assertEqual(response.status_code,200)
        self.assertIn(b'Browse game history',response.data)
        self.assertIn(b'Analyze selected game',response.data)
        gid=bundle['games'][0]['id']
        with self.store.connect() as db:
            self.assertIsNone(db.execute('SELECT id FROM games WHERE user_id=? AND id=?',(self.uid,gid)).fetchone())
        self.assertEqual(self.client.get('/games/'+gid+'/thumbnail.svg').status_code,200)
        other=self.app.test_client();other.get('/');_,token=self.store.login('archive-other','other@example.invalid')
        with other.session_transaction() as session:session['login_token']=token
        self.assertEqual(other.get('/games/'+gid+'/thumbnail.svg').status_code,404)
        self.assertEqual(self.post('/analyze/'+gid).status_code,302)
        self.store.save_import(self.uid,dict(bundle,games=[]),persist_games=False)
        self.assertEqual(self.store.game(self.uid,gid)['id'],gid)
        self.assertEqual(self.client.get('/games/'+gid+'/thumbnail.svg').status_code,200)

    def test_archive_requires_login_and_handles_missing_username_and_errors(self):
        from chess_coach.chesscom import ApiError
        anonymous=self.app.test_client()
        self.assertEqual(anonymous.get('/archive?username=learner').status_code,302)
        self.assertEqual(self.client.get('/archive').status_code,200)
        for error,code in ((ApiError('rate',status=429),429),(ApiError('offline'),502),(ValueError('invalid month'),400)):
            with patch('chess_coach.beta.browse_archive',side_effect=error):
                self.assertEqual(self.client.get('/archive?username=learner').status_code,code)
        self.assertEqual(self.client.get('/archive?username=learner&page=no').status_code,400)

    def test_import_summary_empty_and_api_failure(self):
        bundle={'username':'test','requested_at':1,'games':[],'warnings':['Partial coverage'],
                'summary':{'results':{'win':0,'draw':0,'loss':0},'latest_reported_rapid':None},
                'coverage':{'oldest_imported':None,'newest_imported':None,'truncated':False}}
        with patch('chess_coach.beta.import_history',return_value=bundle):
            self.assertEqual(self.post('/import',data={'username':'test'}).status_code,302)
        page=self.client.get('/').get_data(as_text=True)
        self.assertIn('No eligible games',page);self.assertIn('Partial coverage',page)
        from chess_coach.chesscom import ApiError
        with patch('chess_coach.beta.import_history',side_effect=ApiError('failure')):
            self.assertEqual(self.post('/import',data={'username':'test'}).status_code,502)

    def test_import_failure_messages_distinguish_username_rate_limit_and_tls(self):
        from chess_coach.chesscom import ApiError
        for error,status,text in ((ApiError('missing',status=404),404,'could not find'),
                                  (ApiError('limited',status=429),429,'rate limited'),
                                  (ApiError('certificate',kind='tls'),502,'HTTPS certificate'),
                                  (ApiError('offline',kind='connection'),502,'could not connect')):
            with patch('chess_coach.beta.import_history',side_effect=error):
                response=self.post('/import',data={'username':'test'})
            self.assertEqual(response.status_code,status)
            self.assertIn(text,response.get_data(as_text=True))

    def test_pgn_job_status_and_no_suitable_exercises(self):
        response=self.post('/pgn',data={'pgn':self.snapshot['source']['pgn'],'color':'white'})
        self.assertEqual(response.status_code,302)
        job=self.store.claim();self.store.complete(job,{'exercises':[],'report':{}})
        self.assertIn('No suitable practice positions',self.client.get(response.location).get_data(as_text=True))
        self.assertEqual(self.client.get('/api/jobs/'+job['id']).get_json()['status'],'completed')

    def test_quality_gate_blocks_new_analysis(self):
        self.app.config['AUTOMATIC_EXERCISES_ENABLED']=False
        self.assertEqual(self.post('/pgn',data={'pgn':self.snapshot['source']['pgn'],'color':'white'}).status_code,503)

    def test_local_testing_allows_more_games_but_preserves_active_job_limit(self):
        self.app.config['LOCAL_TESTING']=True
        data={'pgn':self.snapshot['source']['pgn'],'color':'white'}
        self.assertEqual(self.post('/pgn',data=data).status_code,302)
        self.assertEqual(self.post('/pgn',data=data).status_code,409)
        job=self.store.claim()
        self.store.complete(job,{'exercises':[],'report':{}})
        self.assertEqual(self.post('/pgn',data=data).status_code,302)

    def test_public_origin_rejects_local_testing_mode(self):
        with self.assertRaisesRegex(ValueError,'LOCAL_TESTING'):
            create_app({'SECRET_KEY':'s'*64,'DATABASE':str(Path(self.directory.name)/'public'),
                        'APP_ORIGIN':'https://demo.example','LOCAL_DEMO':False,
                        'LOCAL_TESTING':True,'START_SUPERVISOR':False})

    def test_local_testing_import_allowance_and_specific_default_error(self):
        from chess_coach.chesscom import ApiError
        # Accepted failed requests still consume allowance, without network calls.
        with patch('chess_coach.beta.import_history',side_effect=ApiError('offline')):
            for _ in range(5):
                self.assertEqual(self.post('/import',data={'username':'test'}).status_code,502)
            response=self.post('/import',data={'username':'test'})
            self.assertEqual(response.status_code,409)
            self.assertIn('game import allowance reached',response.get_data(as_text=True))
            self.assertIn('00:00 UTC',response.get_data(as_text=True))
            self.app.config['LOCAL_TESTING']=True
            self.assertEqual(self.post('/import',data={'username':'test'}).status_code,502)

    def test_logout_invalidates_server_session(self):
        with self.client.session_transaction() as session:token=session['login_token']
        self.assertEqual(self.post('/logout').status_code,302)
        self.assertIsNone(self.store.user(token))

    def test_local_login_forbidden_with_public_origin(self):
        with self.assertRaises(ValueError):
            create_app({'SECRET_KEY':'test','DATABASE':str(Path(self.directory.name)/'public'),'APP_ORIGIN':'https://demo.example',
                        'LOCAL_DEMO':True,'START_SUPERVISOR':False})

    def test_google_identity_callback_success_failure_and_no_tokens_retained(self):
        from authlib.integrations.flask_client import OAuth
        app=create_app({'TESTING':True,'SECRET_KEY':'oauth','DATABASE':str(Path(self.directory.name)/'oauth'),
                        'GOOGLE_CLIENT_ID':'id','GOOGLE_CLIENT_SECRET':'secret','START_SUPERVISOR':False})
        oauth=app.extensions['google_oauth']
        google=Mock()
        google.authorize_access_token.return_value={'userinfo':{'sub':'subject','email':'test@example.invalid','email_verified':True},'access_token':'DO NOT STORE'}
        client=app.test_client()
        with patch.dict(oauth._clients,{'google':google}):
            self.assertEqual(client.get('/auth/google/callback?code=test&state=test').status_code,302)
            with client.session_transaction() as session:
                self.assertEqual(set(session),{'csrf','login_token'})
            google.authorize_access_token.side_effect=ValueError('bad state')
            self.assertEqual(client.get('/auth/google/callback?code=bad').status_code,400)
