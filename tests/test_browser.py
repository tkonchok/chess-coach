"""Opt-in actual Chromium interactions. No live OAuth or AI provider calls."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch

from beta_fixtures import snapshot


@unittest.skipUnless(os.environ.get('RUN_BROWSER_TESTS') == '1','Set RUN_BROWSER_TESTS=1 and install Chromium')
class BrowserTests(unittest.TestCase):
    def test_archive_month_filter_pagination_selection_and_mobile_layout(self):
        from playwright.sync_api import sync_playwright, expect
        from werkzeug.serving import make_server
        from chess_coach.beta import create_app
        from chess_coach.chesscom import ChessComClient
        from test_chesscom import archived_game, BASE, NOW
        from datetime import datetime, timezone
        old=int(datetime(2020,2,15,tzinfo=timezone.utc).timestamp())
        records=[archived_game(n,end_time=old-n*60,time_class='blitz',rated=False,result='resigned') for n in range(1,124)]
        responses={BASE+'/games/archives':{'archives':[BASE+'/games/2020/02',BASE+'/games/2026/09']},
                   BASE+'/games/2020/02':{'games':records}, BASE+'/games/2026/09':{'games':[archived_game(200)]}}
        def transport(url,headers):return 200,{'Cache-Control':'max-age=3600'},json.dumps(responses[url]).encode()
        with TemporaryDirectory() as directory:
            app=create_app({'TESTING':True,'SECRET_KEY':'archive','DATABASE':str(Path(directory)/'db'),
                            'APP_ORIGIN':'http://127.0.0.1:5050','LOCAL_DEMO':True,'LOCAL_TESTING':True,
                            'AUTOMATIC_EXERCISES_ENABLED':True,'START_SUPERVISOR':False,'GOOGLE_CLIENT_ID':'','GOOGLE_CLIENT_SECRET':''})
            server=make_server('127.0.0.1',0,app,threaded=True)
            origin=f'http://127.0.0.1:{server.server_port}';app.config['APP_ORIGIN']=origin
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                with patch('chess_coach.beta.ChessComClient',side_effect=lambda path,**kw:ChessComClient(path,transport=transport,**kw)), sync_playwright() as playwright:
                    browser=playwright.chromium.launch();page=browser.new_page(viewport={'width':1280,'height':900})
                    page.goto(origin);page.get_by_text('Local development',exact=True).click()
                    page.get_by_role('button',name='Enter local demo').click()
                    page.get_by_role('link',name='Browse game history').click()
                    page.get_by_label('Chess.com username').fill('learner')
                    page.get_by_role('button',name='Browse games').click()
                    expect(page.locator('.game-row')).to_have_count(1)
                    page.get_by_label('Month',exact=True).select_option('2020-02')
                    page.get_by_role('button',name='Browse games').click()
                    expect(page.locator('.game-row')).to_have_count(50)
                    expect(page.get_by_role('status')).to_contain_text('123 games · Page 1 of 3')
                    page.get_by_label('Time control').select_option('rapid');page.get_by_role('button',name='Browse games').click()
                    expect(page.locator('.game-row')).to_have_count(0)
                    page.get_by_label('Time control').select_option('blitz')
                    page.get_by_label('Result',exact=True).select_option('win');page.get_by_role('button',name='Browse games').click()
                    expect(page.locator('.game-row')).to_have_count(0)
                    page.get_by_label('Result',exact=True).select_option('loss');page.get_by_role('button',name='Browse games').click()
                    expect(page.locator('.game-row')).to_have_count(50)
                    page.get_by_role('link',name='Older games').click()
                    expect(page.get_by_role('status')).to_contain_text('Page 2 of 3')
                    page.get_by_role('link',name='Older games').click()
                    expect(page.locator('.game-row')).to_have_count(23)
                    expect(page.get_by_role('status')).to_contain_text('Page 3 of 3')
                    expect(page.get_by_label('Result',exact=True)).to_have_value('loss')
                    self.assertIn('result=loss',page.url)
                    for width,height in ((1280,900),(390,844)):
                        page.set_viewport_size({'width':width,'height':height})
                        self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
                        page.screenshot(path=f'generated/archive-{width}.png',full_page=True)
                    page.get_by_role('button',name='Analyze selected game').first.click()
                    expect(page.locator('#job-status')).to_have_text('Queued')
                    store=app.extensions['store'];uid=store.login('local-demo','local-demo@example.invalid')[0]
                    job=store.job(uid,store.jobs(uid)[0]['id']);gid=job['game_id']
                    page.goto(origin+'/archive?username=learner&month=2026-09')
                    self.assertEqual(store.game(uid,gid)['time_class'],'blitz')
                    page.goto(origin+'/jobs/'+job['id']);expect(page.locator('#job-status')).to_have_text('Queued')
                    browser.close()
            finally:
                server.shutdown();server.server_close();thread.join(timeout=5)

    def test_landing_library_filters_analysis_polling_and_layout(self):
        from playwright.sync_api import sync_playwright, expect
        from werkzeug.serving import make_server
        from chess_coach.beta import create_app
        from uuid import uuid4
        with TemporaryDirectory() as directory:
            app=create_app({'TESTING':True,'SECRET_KEY':'screens','DATABASE':str(Path(directory)/'db'),
                            'APP_ORIGIN':'http://127.0.0.1:5050','LOCAL_DEMO':True,'LOCAL_TESTING':True,
                            'AUTOMATIC_EXERCISES_ENABLED':True,'START_SUPERVISOR':False,'GOOGLE_CLIENT_ID':'','GOOGLE_CLIENT_SECRET':''})
            store=app.extensions['store'];uid,_=store.login('local-demo','local-demo@example.invalid')
            sample=snapshot();store.add_game(uid,{'id':'screen-game','pgn':sample['source']['pgn'],'color':'white'})
            jid=store.enqueue(uid,'screen-game',daily_limit=20)
            server=make_server('127.0.0.1',0,app,threaded=True)
            origin=f'http://127.0.0.1:{server.server_port}';app.config['APP_ORIGIN']=origin
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                with sync_playwright() as playwright:
                    browser=playwright.chromium.launch();page=browser.new_page(viewport={'width':1280,'height':900})
                    page.goto(origin)
                    expect(page.get_by_role('heading',name='Turn your own games into better practice.')).to_be_visible()
                    self.assertEqual(page.locator('.preview-board svg rect.square').count(),64)
                    self.assertGreater(page.locator('.preview-board svg use').count(),0)
                    for width,height in ((1280,900),(390,844)):
                        page.set_viewport_size({'width':width,'height':height})
                        self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
                        page.screenshot(path=f'generated/landing-{width}.png',full_page=True)
                    page.get_by_text('Local development',exact=True).click()
                    page.get_by_role('button',name='Enter local demo').click()
                    page.goto(origin+'/jobs/'+jid)
                    expect(page.locator('#job-status')).to_have_text('Queued')
                    job=store.claim();store.complete(job,{'exercises':[sample],'report':{}})
                    expect(page.locator('#job-status')).to_have_text('Ready',timeout=15000)
                    expect(page.locator('.position-card').first).to_be_visible()
                    expect(page.get_by_role('link',name='Practice next position')).to_have_count(0)
                    for width,height in ((1280,900),(390,844)):
                        page.set_viewport_size({'width':width,'height':height})
                        self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
                        page.screenshot(path=f'generated/analysis-{width}.png',full_page=True)
                    page.get_by_role('link',name='View in Puzzles').click()
                    expect(page.locator('.game-group h2')).to_contain_text('Opponent')
                    expect(page.locator('.game-group .group-heading .badge')).to_have_text('0 of 1 practiced')
                    for width,height in ((1280,900),(390,844)):
                        page.set_viewport_size({'width':width,'height':height})
                        self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
                        page.screenshot(path=f'generated/puzzles-{width}.png',full_page=True)
                    page.get_by_role('link',name='Practiced',exact=True).click()
                    expect(page.get_by_role('heading',name='No practiced positions yet.')).to_be_visible()
                    store.save_attempt(uid,{'submission_id':str(uuid4()),'version_id':sample['version_id'],
                        'proposed_move_uci':'e2e4','original_choice':'','original_reasoning':'','dont_remember':False,
                        'practice_reasoning':'','takeaway':'Review my reply'})
                    page.reload()
                    expect(page.locator('.position-card .badge')).to_have_text('Practiced')
                    page.get_by_role('link',name='To practice',exact=True).click()
                    expect(page.get_by_role('heading',name='All caught up.')).to_be_visible()
                    page.get_by_role('link',name='View all puzzles').click()
                    page.locator('.position-card').first.click()
                    expect(page.locator('#status')).not_to_have_text('Loading the position…')
                    browser.close()
            finally:
                server.shutdown();server.server_close();thread.join(timeout=5)

    def test_walkthrough_promotion_failure_retry_and_stale_commentary(self):
        import chess
        import chess.engine
        from unittest.mock import Mock
        from playwright.sync_api import sync_playwright, expect, Error
        from werkzeug.serving import make_server
        from chess_coach.beta import create_app
        from chess_coach.training import TrainingCard
        from chess_coach.walkthrough import prepare
        card=TrainingCard(0,'7k/8/8/8/8/8/p7/7K w - - 0 1','Kh2',
                          'Choose a move.',('Kh2','a1=Q'),'Illustrative fixture.')
        with TemporaryDirectory() as directory, patch('chess_coach.beta.card_from_exercise',return_value=card):
            app=create_app({'SECRET_KEY':'browser-test','DATABASE':str(Path(directory)/'db'),
                            'LOCAL_DEMO':True,'START_SUPERVISOR':False})
            store=app.extensions['store'];uid,token=store.login('walk','test@example.invalid')
            sample=snapshot();store.retain(uid,sample)
            control={'fail':True};held=[]
            def run(fen,proposed,recommended,reserve):
                reserve()
                if control['fail']:
                    control['fail']=False;raise RuntimeError('Engine busy fixture')
                engine=Mock(id={'name':'Fixture engine'})
                def analyse(board,limit,**kwargs):
                    root=kwargs['root_moves'][0];replay=board.copy();pv=[root];replay.push(root)
                    move=chess.Move.from_uci('a2a1q');pv.append(move);replay.push(move)
                    while len(pv) < 6 and not replay.is_game_over():
                        move=next(iter(replay.legal_moves));pv.append(move);replay.push(move)
                    return {'pv':pv,'score':chess.engine.PovScore(chess.engine.Cp(100),board.turn),'depth':10}
                engine.analyse.side_effect=analyse
                return prepare(engine,fen,proposed,recommended)
            supervisor=Mock();supervisor.walkthrough.side_effect=run
            app.extensions['supervisor']=supervisor
            server=make_server('127.0.0.1',0,app,threaded=True)
            origin=f'http://127.0.0.1:{server.server_port}';app.config['APP_ORIGIN']=origin
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                with sync_playwright() as playwright:
                    browser=playwright.chromium.launch();context=browser.new_context(viewport={'width':1280,'height':900},has_touch=True)
                    with app.test_request_context():
                        cookie=app.session_interface.get_signing_serializer(app).dumps({'login_token':token,'csrf':'walk'})
                    context.add_cookies([{'name':'session','value':cookie,'url':origin}])
                    page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                    # A slow provider must never block stepping or saving.
                    page.route('**/api/walkthrough/commentary',lambda route:held.append(route))
                    page.route('**/api/engine',lambda route:route.fulfill(status=503,json={'error':'Live engine unavailable fixture'}))
                    page.goto(origin+'/practice/'+sample['version_id'])
                    expect(page.locator('#status')).not_to_have_text('Loading the position…')
                    page.evaluate('interactiveCoach = false; render()')
                    page.locator('[data-square="h1"]').click();page.locator('[data-square="h2"]').click()
                    page.locator('#reveal').click()
                    page.locator('#tab-reflection').click();page.locator('#takeaway').fill('Keep my draft')
                    page.locator('#tab-coaching').click();page.evaluate('startWalkthrough()')
                    expect(page.locator('#status')).to_contain_text('Engine busy fixture')
                    expect(page.locator('#takeaway')).to_have_value('Keep my draft')
                    self.assertEqual(page.evaluate('path.length'),0)
                    page.evaluate('startWalkthrough()')
                    expect(page.locator('#walk-count')).to_have_text('0 / 6')
                    expect(page.locator('#walk-recommended')).not_to_be_visible()
                    page.locator('#walk-next').click();expect(page.locator('#walk-count')).to_have_text('1 / 6')
                    page.locator('#walk-next').click();expect(page.locator('#walk-count')).to_have_text('2 / 6')
                    expect(page.locator('#walk-text')).to_contain_text('promotes to a queen')
                    expect(page.locator('#proposal')).to_have_text('Your proposed move: Kh2')
                    self.assertGreater(page.locator('.coach-highlight').count(),0)
                    page.locator('#walk-previous').click();expect(page.locator('#walk-count')).to_have_text('1 / 6')
                    expect(page.locator('#walk-text')).not_to_contain_text('promotes')
                    info=page.get_by_role('button',name='About coaching and privacy')
                    info.focus();expect(page.locator('#coach-info-panel')).to_be_visible()
                    page.keyboard.press('Escape');expect(page.locator('#coach-info-panel')).not_to_be_visible()
                    info.click();expect(page.locator('#coach-info-panel')).to_be_visible()
                    page.keyboard.press('Escape')
                    self.assertEqual(len(held),1)
                    old=held[0];old_data=old.request.post_data_json
                    page.locator('#walk-free').click()
                    old.fulfill(json={'card_id':old_data['card_id'],'walkthrough_id':old_data['walkthrough_id'],
                                      'available':True,'steps':[{'branch':'your','ply':1,'text':'STALE COMMENT','fact_ids':['move'],'move_references':[]}]})
                    page.wait_for_timeout(100)
                    self.assertIsNone(page.evaluate('walkthrough'))
                    expect(page.locator('#walk-text')).not_to_contain_text('STALE COMMENT')
                    page.evaluate('startWalkthrough()')
                    expect(page.locator('#walk-count')).to_have_text('0 / 6')
                    page.wait_for_timeout(100)
                    self.assertEqual(len(held),2)
                    evidence=page.evaluate('walkthrough.evidence')
                    steps=[{'branch':b['id'],'ply':step['ply'],'text':f'COMMENT STEP {step["ply"]}',
                            'fact_ids':['move'],'move_references':[]} for b in evidence['branches'] for step in b['steps']]
                    data=held[-1].request.post_data_json
                    self.assertEqual(set(data),{'card_id','walkthrough_id','proposed_move_uci','consent'})
                    held[-1].fulfill(json={'card_id':data['card_id'],'walkthrough_id':data['walkthrough_id'],'available':True,'steps':steps})
                    expect(page.locator('#commentary-status')).to_contain_text('AI commentary is available')
                    expect(page.locator('#walk-text')).not_to_contain_text('COMMENT STEP')
                    page.locator('#walk-next').focus();page.keyboard.press('Enter')
                    expect(page.locator('#walk-text')).to_have_text('COMMENT STEP 1')
                    expect(page.locator('#walk-text')).not_to_contain_text('COMMENT STEP 2')
                    page.locator('#walk-next').click()
                    expect(page.locator('#walk-text')).to_have_text('COMMENT STEP 2')
                    page.set_viewport_size({'width':390,'height':844})
                    info.tap()
                    expect(page.locator('#coach-info-panel')).to_be_visible()
                    self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
                    board=page.locator('#board').bounding_box();bar=page.locator('#eval-bar').bounding_box()
                    self.assertAlmostEqual(board['height'],bar['height'],delta=1)
                    self.assertEqual(errors,[]);browser.close()
            finally:
                server.shutdown();server.server_close();thread.join(timeout=5)

    def test_real_games_browser_analysis_save_history_and_failure_retry(self):
        from playwright.sync_api import sync_playwright, expect
        from werkzeug.serving import make_server
        from chess_coach.beta import create_app
        with TemporaryDirectory() as directory:
            app=create_app({'SECRET_KEY':'browser-test','DATABASE':str(Path(directory)/'db'),
                            'LOCAL_DEMO':True,'AUTOMATIC_EXERCISES_ENABLED':True,'START_SUPERVISOR':True})
            server=make_server('127.0.0.1',0,app,threaded=True)
            origin=f'http://127.0.0.1:{server.server_port}'
            app.config['APP_ORIGIN']=origin
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                with sync_playwright() as playwright:
                    browser=playwright.chromium.launch()
                    context=browser.new_context(record_video_dir='generated/browser-video',viewport={'width':1280,'height':900})
                    page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                    for color in ('white','black'):
                        if color == 'black':
                            # Separate account has its own daily quota. Authentication is
                            # injected only into this temporary test browser, never an app route.
                            _,token=app.extensions['store'].login('browser:black','black@example.invalid')
                            with app.test_request_context():
                                cookie=app.session_interface.get_signing_serializer(app).dumps({'login_token':token,'csrf':'browser-black'})
                            context.add_cookies([{'name':'session','value':cookie,'url':origin}])
                        page.goto(origin)
                        if color == 'white':
                            page.get_by_text('Local development',exact=True).click()
                            page.get_by_role('button',name='Enter local demo').click()
                            self.assertEqual(page.locator('#pgn').count(),1,page.locator('body').inner_text())
                        pgn=(Path(__file__).parent/'fixtures'/f'rapid-{color}.pgn').read_text()
                        if color == 'white':
                            page.get_by_text('Have a PGN? Paste a game',exact=True).click()
                            page.locator('#pgn').fill(pgn)
                            page.locator('#color').select_option(color)
                            page.get_by_role('button',name='Analyze this game',exact=True).click()
                        else:
                            # The HTTP importer response is fixed for repeatability;
                            # selection, queue, Stockfish and persistence are real.
                            bundle={'username':'sample','requested_at':1,'warnings':['Fixture coverage'],
                                    'summary':{'results':{'win':1,'draw':0,'loss':0},'latest_reported_rapid':None},
                                    'coverage':{'oldest_imported':1,'newest_imported':1,'truncated':False},
                                    'games':[{'id':'black-real','pgn':pgn,'color':'black','url':None,
                                              'end_time':1,'opponent':'Anonymized','result':'win','rating':None}]}
                            page.locator('#username').fill('sample')
                            with patch('chess_coach.beta.import_history',return_value=bundle):
                                page.get_by_role('button',name='Import games',exact=True).click()
                                expect(page.get_by_role('button',name='Analyze selected game')).to_be_visible()
                            page.get_by_role('button',name='Analyze selected game').click()
                        expect(page.get_by_role('link',name='Practice 1',exact=False)).to_be_visible(timeout=240000)
                        page.locator('.position-card img').first.scroll_into_view_if_needed()
                        expect(page.locator('.position-card img').first).to_be_visible()
                        page.wait_for_function('Array.from(document.querySelectorAll(".position-card img")).some(img => img.complete && img.naturalWidth > 0)')
                        page.get_by_role('link',name='Practice 1',exact=False).click()
                        expect(page.locator('#status')).not_to_have_text('Loading the position…')
                        page.evaluate('interactiveCoach = false; render()')
                        self.assertEqual(page.locator('.file-labels span').all_text_contents(),list('abcdefgh' if color == 'white' else 'hgfedcba'))
                        self.assertEqual(page.locator('.rank-labels span').all_text_contents(),[str(n) for n in (range(8,0,-1) if color == 'white' else range(1,9))])
                        self.assertEqual(page.locator('template[data-piece]').evaluate_all(
                            '(templates) => templates.reduce((n, t) => n + t.content.querySelectorAll("[style]").length, 0)'),0)
                        for side,fill in [('white','rgb(255, 255, 255)'),('black','rgb(0, 0, 0)')]:
                            knights=page.locator(f'.piece svg g.{side}.knight path:first-child')
                            if knights.count():
                                self.assertEqual(knights.first.evaluate('(p) => getComputedStyle(p).fill'),fill)
                        # Use the legal source move; browser still performs actual selection.
                        state=page.request.get(page.url+'/api/position').json()
                        first=state['legal_moves'][0]
                        page.locator(f'[data-square="{first[:2]}"]').click()
                        page.locator(f'[data-square="{first[2:4]}"]').click()
                        expect(page.locator('#proposal')).to_be_visible()
                        proposed_text=page.locator('#proposal').inner_text()
                        page.get_by_role('button',name='Reveal engine example').click()
                        expect(page.locator('#example')).to_be_visible()
                        expect(page.locator('#engine-state')).to_contain_text('Best for',timeout=10000)
                        expect(page.get_by_label('Best-move arrow',exact=True)).not_to_be_checked()
                        expect(page.locator('#engine-arrow')).not_to_be_visible()
                        page.get_by_label('Best-move arrow',exact=True).check()
                        expect(page.locator('#engine-arrow')).to_be_visible()
                        expect(page.locator('#engine-score')).not_to_have_text('—')
                        page.get_by_label('Best-move arrow',exact=True).uncheck()
                        expect(page.locator('#engine-arrow')).not_to_be_visible()
                        page.get_by_label('Best-move arrow',exact=True).check()
                        page.locator('#next').click()
                        expect(page.locator('#engine-state')).to_contain_text('Best for '+('black' if color == 'white' else 'white'),timeout=10000)
                        page.locator('#previous').click()
                        expect(page.locator('#engine-state')).to_contain_text('Best for '+color,timeout=10000)
                        page.screenshot(path=f'generated/compact-{color}-coaching.png',full_page=True)
                        self.assertTrue(page.evaluate('document.documentElement.scrollHeight <= window.innerHeight'))
                        self.assertTrue(page.locator('.board-panel').evaluate('(panel) => panel.scrollHeight <= panel.clientHeight + 1'))
                        board_box=page.locator('#board').bounding_box();bar_box=page.locator('#eval-bar').bounding_box()
                        self.assertAlmostEqual(board_box['height'],bar_box['height'],delta=1)
                        self.assertGreater(bar_box['x'],board_box['x']+board_box['width'])
                        page.evaluate('startWalkthrough()')
                        expect(page.locator('#walk-navigation')).to_be_visible(timeout=15000)
                        expect(page.locator('#walk-count')).to_contain_text('0 /')
                        self.assertEqual(page.evaluate('path.length'),0)
                        steps=page.evaluate('walkBranch().steps.length')
                        for ply in range(1,steps+1):
                            page.get_by_role('button',name='Next move',exact=True).click()
                            expect(page.locator('#walk-count')).to_have_text(f'{ply} / {steps}')
                            expect(page.locator('#walk-text')).not_to_have_text('')
                            expect(page.locator('#proposal')).to_have_text(proposed_text)
                        expect(page.locator('#walk-next')).to_be_disabled()
                        page.screenshot(path=f'generated/walkthrough-{color}-desktop.png',full_page=True)
                        page.locator('#walk-recommended').click()
                        expect(page.locator('#walk-count')).to_contain_text('0 /')
                        self.assertEqual(page.evaluate('path.length'),0)
                        page.locator('#walk-next').click()
                        expect(page.locator('#walk-count')).to_contain_text('1 /')
                        page.locator('#walk-your').click()
                        expect(page.locator('#walk-count')).to_contain_text('0 /')
                        info=page.get_by_role('button',name='About coaching and privacy')
                        info.hover();expect(page.locator('#coach-info-panel')).to_be_visible()
                        expect(page.locator('#commentary-status')).to_contain_text('Board facts',timeout=10000)
                        page.locator('#board').hover()
                        page.locator('#walk-reflect').click()
                        page.get_by_role('tab',name='Reflection & save').click()
                        self.assertEqual(page.locator('input[name="reflection-choice"]:checked').count(),0)
                        page.get_by_label('I miscalculated',exact=True).check()
                        expect(page.get_by_label('I miscalculated',exact=True)).to_be_checked()
                        page.get_by_label('I miscalculated',exact=True).focus()
                        page.keyboard.press('ArrowRight')
                        expect(page.get_by_label('Missed a threat',exact=True)).to_be_checked()
                        page.keyboard.press('ArrowLeft')
                        expect(page.get_by_label('I miscalculated',exact=True)).to_be_checked()
                        page.get_by_role('button',name='Skip reflection choice').click()
                        self.assertEqual(page.locator('input[name="reflection-choice"]:checked').count(),0)
                        page.get_by_label('I miscalculated',exact=True).check()
                        page.screenshot(path=f'generated/stitch-practice-{color}-desktop.png',full_page=True)
                        page.locator('#takeaway').fill('Check the opponent reply. ♟')
                        # Fail the first save, then retry after restoring the endpoint.
                        page.route('**/api/attempts',lambda route:route.fulfill(status=503,content_type='application/json',body='{"error":"Test outage"}'))
                        page.get_by_role('button',name='Save and finish').click()
                        expect(page.locator('#status')).to_contain_text('Test outage')
                        expect(page.locator('#takeaway')).to_have_value('Check the opponent reply. ♟')
                        page.unroute('**/api/attempts')
                        page.get_by_role('button',name='Save and finish').click()
                        expect(page.locator('#finish-note a')).to_be_visible()
                        page.locator('#finish-note a').click()
                        expect(page.locator('dd').last).to_have_text('Check the opponent reply. ♟')
                        expect(page.locator('dd').nth(1)).to_have_text('miscalculated')
                        page.get_by_role('link',name='Open original exercise / Try again').click()
                        expect(page.locator('#status')).not_to_have_text('Loading the position…')
                        page.set_viewport_size({'width':390,'height':844})
                        self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
                        page.screenshot(path=f'generated/browser-{color}.png',full_page=True)
                        page.set_viewport_size({'width':1280,'height':900})
                        # Default coach mode automatically prepares and plays the reply.
                        state=page.request.get(page.url+'/api/position').json()
                        first=state['legal_moves'][0]
                        page.locator(f'[data-square="{first[:2]}"]').click()
                        page.locator(f'[data-square="{first[2:4]}"]').click()
                        page.wait_for_function('() => walkthrough && walkthrough.ply >= 2 && !busy',timeout=30000)
                        self.assertEqual(page.evaluate('path.length'),2)
                        if page.evaluate("walkBranch().steps.map(step => step.uci).join(' ') === example.moves.join(' ')"):
                            expect(page.locator('#recommended-line')).not_to_be_visible()
                            expect(page.locator('#example-line')).to_be_visible()
                            expect(page.locator('#branch-line-label')).not_to_be_visible()
                        else:
                            expect(page.locator('#recommended-line')).to_be_visible()
                            expect(page.locator('#branch-line-label')).to_be_visible()
                        page.locator('#coach-prev').click()
                        page.wait_for_function('() => path.length === 1 && !busy')
                        self.assertTrue(page.evaluate('coachBrowsing'))
                        page.locator('#coach-next').click()
                        page.wait_for_function('() => path.length === 2 && !busy')
                        self.assertFalse(page.evaluate('coachBrowsing'))
                        expect(page.locator('#walk-navigation')).not_to_be_visible()
                        expect(page.locator('#walk-text')).to_contain_text('Your turn')
                        if color == 'black':
                            alternative=page.evaluate('position.legal_moves.find(move => move !== (walkthrough ? walkBranch().steps[walkthrough.ply]?.uci : null) && move.length === 4)')
                            self.assertIsNotNone(alternative)
                            page.locator(f'[data-square="{alternative[:2]}"]').click()
                            page.locator(f'[data-square="{alternative[2:4]}"]').click()
                            expect(page.locator('#walk-text')).to_contain_text('Engine reply:',timeout=15000)
                            page.wait_for_function('() => !busy')
                            self.assertEqual(page.evaluate('path.length'),4)
                            page.locator('#coach-back').click()
                            page.wait_for_function('() => !busy')
                            self.assertEqual(page.evaluate('path.length'),2)
                        while not page.evaluate('coachFinished'):
                            ply=page.evaluate('walkthrough.ply')
                            expected=page.evaluate('walkBranch().steps[walkthrough.ply].uci')
                            page.locator(f'[data-square="{expected[:2]}"]').click()
                            page.locator(f'[data-square="{expected[2:4]}"]').click()
                            page.wait_for_function('(ply) => walkthrough.ply > ply && !busy',arg=ply)
                            expect(page.locator('#walk-text')).to_contain_text('Matches the engine line')
                        expect(page.locator('#coach-save')).to_be_visible()
                        # The first move after the prepared line ends must still
                        # receive an opponent reply without any mode button.
                        extra=page.evaluate('position.legal_moves.find(move => move.length === 4)')
                        if extra and not page.evaluate('position.outcome'):
                            before=page.evaluate('path.length')
                            page.locator(f'[data-square="{extra[:2]}"]').click()
                            page.locator(f'[data-square="{extra[2:4]}"]').click()
                            page.wait_for_function('(before) => !busy && (path.length === before + 2 || position.outcome)',arg=before)
                            self.assertFalse(page.evaluate('selfAnalysis'))
                            self.assertIsNone(page.evaluate('walkthrough'))
                            page.locator('#coach-back').click()
                            page.wait_for_function('() => !busy')
                            self.assertEqual(page.evaluate('path.length'),before)
                        if page.locator('#coach-compare').is_visible():
                            page.locator('#coach-compare').click()
                            page.wait_for_function("() => !busy && path.length === 2")
                            alternative=page.evaluate('position.legal_moves.find(move => move !== (walkthrough ? walkBranch().steps[walkthrough.ply]?.uci : null) && move.length === 4)')
                            if alternative and not page.evaluate('coachFinished'):
                                page.locator(f'[data-square="{alternative[:2]}"]').click()
                                page.locator(f'[data-square="{alternative[2:4]}"]').click()
                                expect(page.locator('#walk-text')).to_contain_text('Engine reply:')
                                page.wait_for_function('() => !busy')
                                page.locator('#coach-back').click()
                                page.wait_for_function('() => !busy')
                        page.locator('#coach-save').click()
                        expect(page.locator('#takeaway')).to_be_visible()
                        self.assertTrue(page.evaluate('document.documentElement.scrollHeight <= window.innerHeight'))
                        board_box=page.locator('#board').bounding_box();bar_box=page.locator('#eval-bar').bounding_box()
                        self.assertAlmostEqual(board_box['height'],bar_box['height'],delta=1)
                        page.screenshot(path=f'generated/interactive-{color}-desktop.png',full_page=True)
                        page.locator('#tab-coaching').click()
                        before=page.evaluate('path.length')
                        page.get_by_role('button',name='Self analysis',exact=True).click()
                        page.wait_for_function('() => selfAnalysis && !busy')
                        self.assertEqual(page.evaluate('path.length'),before)
                        expect(page.locator('#recommended-line')).to_be_visible()
                        expect(page.locator('#example-line')).not_to_be_visible()
                        expect(page.get_by_label('Best-move arrow',exact=True)).to_be_checked()
                        if not page.evaluate('position.outcome'):
                            expect(page.locator('#engine-arrow')).to_be_visible(timeout=15000)
                        for _ in range(2):
                            move=page.evaluate('position.legal_moves.find(move => move.length === 4)')
                            if not move: break
                            page.locator(f'[data-square="{move[:2]}"]').click()
                            page.locator(f'[data-square="{move[2:4]}"]').click()
                            before+=1
                            page.wait_for_function('(length) => path.length === length && !busy',arg=before)
                            self.assertIsNone(page.evaluate('walkthrough'))
                        page.get_by_role('button',name='Self analysis',exact=True).click()
                        page.wait_for_function('() => !selfAnalysis && !busy')
                        move=page.evaluate('position.legal_moves.find(move => move.length === 4)')
                        if move:
                            page.locator(f'[data-square="{move[:2]}"]').click()
                            page.locator(f'[data-square="{move[2:4]}"]').click()
                            page.wait_for_function('(length) => !busy && (path.length === length + 2 || position.outcome)',arg=before,timeout=15000)

                    self.assertEqual(errors,[])
                    context.close();browser.close()
            finally:
                server.shutdown();server.server_close();thread.join(timeout=5)
                app.extensions['supervisor'].close()

    def test_keyboard_underpromotion_reveal_and_navigation(self):
        from playwright.sync_api import sync_playwright, expect
        from werkzeug.serving import make_server
        from chess_coach.web import create_app
        from chess_coach.training import TrainingCard
        card=TrainingCard(0,'7k/P7/8/8/8/8/8/7K w - - 0 1','a8=Q+',
                          'Choose a move.',('a8=Q+',),'Illustrative promotion example.')
        server=make_server('127.0.0.1',0,create_app(card),threaded=True)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as playwright:
                browser=playwright.chromium.launch();page=browser.new_page()
                page.goto(f'http://127.0.0.1:{server.server_port}')
                expect(page.locator('#status')).not_to_have_text('Loading the position…')
                page.locator('[data-square="a7"]').focus()
                page.keyboard.press('Enter');page.keyboard.press('ArrowUp');page.keyboard.press('Enter')
                expect(page.locator('#promotion')).to_be_visible()
                page.get_by_role('button',name='Cancel',exact=True).click()
                expect(page.locator('#promotion')).not_to_be_visible()
                page.locator('[data-square="a7"]').focus()
                page.keyboard.press('Enter');page.keyboard.press('ArrowUp');page.keyboard.press('Enter')
                page.get_by_role('button',name='Knight',exact=True).click()
                expect(page.locator('#proposal')).to_contain_text('a8=N')
                page.get_by_role('button',name='Reveal reviewed example').click()
                expect(page.locator('#example')).to_be_visible()
                page.locator('#next').click()
                expect(page.locator('#step-count')).to_contain_text('1')
                page.locator('#previous').click()
                expect(page.locator('#step-count')).to_contain_text('0')
                expect(page.locator('#proposal')).to_contain_text('a8=N')
                browser.close()
        finally:
            server.shutdown();server.server_close();thread.join(timeout=5)
