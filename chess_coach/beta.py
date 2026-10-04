"""Authenticated beta adapter. Existing local practice adapter stays available."""

from datetime import datetime, timezone
from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path
import secrets
import sqlite3
import chess
from urllib.parse import urlparse
from urllib.error import HTTPError, URLError

from flask import Flask, Response, abort, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.exceptions import HTTPException, BadRequest, NotFound, ServiceUnavailable, Conflict as HttpConflict

from chess_coach.chesscom import ApiError, ChessComClient, import_history, browse_archive
from chess_coach.coaching import coach, validate_response, coach_walkthrough, validate_walkthrough
from chess_coach.exercises import card_from_exercise
from chess_coach.jobs import Supervisor
from chess_coach.library import game_metadata, grouped_library, position_items
from chess_coach.live import replay_moves, terminal_result
from chess_coach.storage import Conflict, Store
from chess_coach.web import create_app as practice_adapter
from chess_coach.workflow import pgn_digest, validated_game
from chess_coach.walkthrough import digest as walkthrough_digest
from chess_coach.thumbnails import board_thumbnail


def create_app(config=None):
    app = Flask(__name__)
    origin = os.environ.get('APP_ORIGIN', 'http://127.0.0.1:5050').rstrip('/')
    app.config.update(SECRET_KEY=os.environ.get('SECRET_KEY'), APP_ORIGIN=origin,
        DATABASE=os.environ.get('DATABASE', str(Path(app.instance_path) / 'chess-coach.sqlite3')),
        GOOGLE_CLIENT_ID=os.environ.get('GOOGLE_CLIENT_ID'), GOOGLE_CLIENT_SECRET=os.environ.get('GOOGLE_CLIENT_SECRET'),
        GROQ_API_KEY=os.environ.get('GROQ_API_KEY'), GROQ_MODEL=os.environ.get('GROQ_MODEL', 'openai/gpt-oss-120b'),
        STOCKFISH_PATH=os.environ.get('STOCKFISH_PATH', 'stockfish'), START_SUPERVISOR=True,
        LOCAL_DEMO=os.environ.get('LOCAL_DEMO') == '1',
        LOCAL_TESTING=os.environ.get('LOCAL_TESTING') == '1',
        WALKTHROUGH_AI_ENABLED=os.environ.get('WALKTHROUGH_AI_ENABLED') == '1',
        AUTOMATIC_EXERCISES_ENABLED=os.environ.get('AUTOMATIC_EXERCISES_ENABLED') == '1',
        MAX_CONTENT_LENGTH=1_100_000, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=origin.startswith('https://'))
    if config:
        app.config.update(config)
    parsed = urlparse(app.config['APP_ORIGIN'])
    local = parsed.hostname in ('127.0.0.1', 'localhost') and parsed.scheme == 'http'
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.path not in ('','/'):
        raise ValueError('APP_ORIGIN must be an absolute origin without a path')
    if not local and (parsed.scheme != 'https' or app.config['LOCAL_DEMO']):
        raise ValueError('Public hosting requires HTTPS and forbids LOCAL_DEMO')
    if app.config['LOCAL_TESTING'] and not local:
        raise ValueError('LOCAL_TESTING is only permitted on localhost')
    if not app.config['SECRET_KEY']:
        if local and app.config['LOCAL_DEMO']:
            app.config['SECRET_KEY'] = secrets.token_hex(32)
        else:
            raise ValueError('Set SECRET_KEY to a random secret before starting')
    app.config['SESSION_COOKIE_SECURE'] = not local
    if not local and (len(app.config['SECRET_KEY']) < 32 or app.config['SECRET_KEY'] == 'replace-with-a-random-secret'):
        raise ValueError('Public hosting requires a random SECRET_KEY of at least 32 characters')
    # Railway probes use this Host header rather than the generated public URL.
    app.config['TRUSTED_HOSTS'] = ['localhost','127.0.0.1'] if local else [parsed.hostname,'healthcheck.railway.app']
    store = Store(app.config['DATABASE'])
    app.extensions['store'] = store
    if app.config['START_SUPERVISOR']:
        app.extensions['supervisor'] = Supervisor(store, app.config['STOCKFISH_PATH'])

    oauth = None
    if app.config['GOOGLE_CLIENT_ID'] and app.config['GOOGLE_CLIENT_SECRET']:
        from authlib.integrations.flask_client import OAuth
        oauth = OAuth(app)
        oauth.register('google', server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
                       client_kwargs={'scope': 'openid email', 'timeout': 15})
    app.extensions['google_oauth'] = oauth

    @app.before_request
    def guard():
        if request.routing_exception is not None:
            return None
        g.user_id = store.user(session.get('login_token'))
        session.setdefault('csrf', secrets.token_urlsafe(32))
        if request.method not in ('GET','HEAD','OPTIONS'):
            if request.headers.get('Sec-Fetch-Site') == 'cross-site':
                abort(403)
            origin_header = request.headers.get('Origin')
            if origin_header and origin_header != app.config['APP_ORIGIN']:
                abort(403)
            token = request.headers.get('X-CSRF-Token') or request.form.get('csrf')
            if not token or not secrets.compare_digest(token, session['csrf']):
                abort(403, 'Session expired or missing CSRF token; reload and try again')
        if request.endpoint not in ('home','login','authorize','local_login','static','health') and not g.user_id:
            if '/api/' in request.path or request.path.startswith('/api/'):
                abort(401, 'Sign in before continuing')
            return redirect(url_for('home'))

    @app.context_processor
    def context():
        return {'csrf_token': session.get('csrf',''), 'beta_mode': True,
                'version_id': getattr(g, 'version_id', ''), 'signed_in': bool(getattr(g,'user_id',None))}

    @app.after_request
    def security(response):
        response.headers.update({'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self' https://accounts.google.com",
            'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY', 'Referrer-Policy': 'same-origin', 'Cache-Control': 'no-store'})
        if not local:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        return response

    @app.errorhandler(HTTPException)
    def http_error(error):
        if request.routing_exception is not None or '/api/' in request.path or request.path.startswith('/api/'):
            return jsonify(error=error.description), error.code
        return render_template('beta_message.html', title='Could not complete that action', message=error.description), error.code

    @app.errorhandler(ValueError)
    def invalid(error):
        return http_error(BadRequest(str(error)))

    @app.errorhandler(KeyError)
    def missing(error):
        abort_error = NotFound('Item not found')
        return http_error(abort_error)

    @app.errorhandler(Conflict)
    def conflict(error):
        return http_error(HttpConflict(str(error)))

    @app.errorhandler(sqlite3.OperationalError)
    def database_busy(error):
        return http_error(ServiceUnavailable('Storage temporarily unavailable; your unsaved notes are unchanged'))

    @app.get('/health')
    def health():
        with store.connect() as db:
            db.execute('SELECT 1')
        return jsonify(status='ok')

    @app.get('/')
    def home():
        bundle = store.imported(g.user_id) if g.user_id else None
        return render_template('beta_home.html', landing_board=board_thumbnail(chess.Board('r1bqk2r/ppp2ppp/2np1n2/4p3/2B1P3/2NP1N2/PPP2PPP/R1BQ1RK1 w kq - 0 7'),'white'), analyzed=store.completed_game_jobs(g.user_id) if g.user_id else {}, bundle=bundle if bundle and 'archive' not in bundle else None, archive_user=bundle['username'] if bundle else None, jobs=store.jobs(g.user_id) if g.user_id else [],
                               local_demo=app.config['LOCAL_DEMO'], google_available=oauth is not None,
                               automatic_enabled=app.config['AUTOMATIC_EXERCISES_ENABLED'])

    @app.post('/login')
    def login():
        if oauth is None:
            abort(503, 'Google sign-in is not configured yet')
        return oauth.google.authorize_redirect(app.config['APP_ORIGIN'] + '/auth/google/callback')

    def establish(subject, email):
        if session.get('login_token'):
            store.logout(session['login_token'])
        _, token = store.login(subject, email)
        session.clear()
        session.update(login_token=token, csrf=secrets.token_urlsafe(32))
        return redirect(url_for('home'))

    @app.get('/auth/google/callback')
    def authorize():
        if oauth is None:
            abort(503)
        try:
            token = oauth.google.authorize_access_token()  # Authlib verifies state, signature, audience and nonce.
            info = token['userinfo']
            if info.get('email_verified') is not True or not isinstance(info.get('sub'), str) or not isinstance(info.get('email'), str):
                raise ValueError('Verified identity required')
        except Exception:
            session.clear()
            abort(400, 'Google sign-in failed or expired; start again')
        return establish('google:' + info['sub'], info['email'])

    @app.post('/local-login')
    def local_login():
        if not app.config['LOCAL_DEMO'] or not local:
            abort(404)
        return establish('local-demo', 'local-demo@example.invalid')

    @app.post('/logout')
    def logout():
        store.logout(session['login_token'])
        session.clear()
        return redirect(url_for('home'))

    @app.post('/import')
    def import_games():
        # Reserve daily bounded import allowance before network calls.
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            store._quota(db, g.user_id, 'import', 20 if app.config['LOCAL_TESTING'] else 5, 100)
        try:
            client = ChessComClient(Path(app.config['DATABASE']).parent / 'import-cache' / g.user_id)
            bundle = import_history(client, request.form.get('username',''), refresh=request.form.get('refresh') == 'on')
        except ApiError as error:
            if error.status in (404, 410):
                abort(404, 'Chess.com could not find that username or its game archive. Check the username, or use PGN.')
            if error.status == 429:
                abort(429, 'Chess.com rate limited this import. Wait before retrying, or use PGN.')
            if error.kind == 'tls':
                abort(502, 'The server could not verify Chess.com’s HTTPS certificate. Check the server certificate setup, or use PGN.')
            if error.kind == 'connection':
                abort(502, 'The server could not connect to Chess.com. Check the connection and try later, or use PGN.')
            abort(502, 'Chess.com import failed or returned unexpected data. Try later, or use PGN.')
        store.save_import(g.user_id, bundle)
        return redirect(url_for('home'))

    @app.get('/archive')
    def archive():
        bundle = store.imported(g.user_id)
        username = request.args.get('username') or (bundle['username'] if bundle else '')
        if not username:
            return render_template('beta_archive.html',bundle={'username':'','games':[], 'warnings':[],
                'archive':{'months':[],'month':None,'page':1,'pages':1,'total':0,'time_class':'all','result':'all'}},
                analyzed={},automatic_enabled=app.config['AUTOMATIC_EXERCISES_ENABLED'])
        # Browse on demand, never enqueue an analysis or import an entire history.
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            store._quota(db, g.user_id, 'archive', 200 if app.config['LOCAL_TESTING'] else 60, 600)
        client = ChessComClient(Path(app.config['DATABASE']).parent / 'import-cache' / g.user_id, max_requests=2)
        try:
            page = int(request.args.get('page','1'))
            result = browse_archive(client, username, month=request.args.get('month') or None,
                                    page=page, time_class=request.args.get('time_class','all'),
                                    result=request.args.get('result','all'))
        except ApiError as error:
            abort(429 if error.status == 429 else 502,
                  'Chess.com archive unavailable. Try later or use PGN; saved puzzles remain available.')
        store.save_import(g.user_id,result,persist_games=False)
        return render_template('beta_archive.html',bundle=result,analyzed=store.completed_game_jobs(g.user_id),
                               automatic_enabled=app.config['AUTOMATIC_EXERCISES_ENABLED'])

    @app.post('/pgn')
    def upload_pgn():
        if not app.config['AUTOMATIC_EXERCISES_ENABLED']:
            abort(503, 'Automatic practice is awaiting its teaching-quality review')
        pgn = request.form.get('pgn','')
        game = validated_game(pgn)
        color = request.form.get('color')
        if color not in ('white','black') or game.headers.get('Result') not in ('1-0','0-1','1/2-1/2'):
            raise ValueError('Choose your color and a completed standard game')
        gid = pgn_digest(pgn) + ':' + color
        store.add_game(g.user_id, {'id':gid, 'pgn':pgn, 'color':color, 'url':None})
        return enqueue(gid)

    def enqueue(gid):
        game = store.game(g.user_id, gid)
        existing = store.completed_game_jobs(g.user_id).get(gid)
        if existing:
            return redirect(url_for('job_page', jid=existing))
        if not app.config['AUTOMATIC_EXERCISES_ENABLED']:
            abort(503, 'Automatic practice is awaiting its teaching-quality review')
        store.add_game(g.user_id, game)  # Preserve the selected archive game beyond page navigation.
        return redirect(url_for('job_page', jid=store.enqueue(g.user_id, gid,
                            daily_limit=20 if app.config['LOCAL_TESTING'] else 1)))

    @app.post('/analyze/<path:gid>')
    def analyze(gid):
        return enqueue(gid)

    @app.get('/jobs/<jid>')
    def job_page(jid):
        job = store.job(g.user_id,jid)
        try:
            game = store.game(g.user_id,job['game_id'])
            parsed = validated_game(game['pgn'])
            source = {'id':pgn_digest(game['pgn']),'headers':dict(parsed.headers)}
            color = game['color']
            thumbnail = url_for('game_thumbnail',gid=job['game_id'])
        except KeyError:
            exercises = (job['result'] or {}).get('exercises',[])
            source = exercises[0]['source'] if exercises else {'id':job['game_id'],'headers':{}}
            color = exercises[0]['player_color'] if exercises else 'unknown'
            thumbnail = url_for('exercise_thumbnail',version=exercises[0]['version_id']) if exercises else None
        saved = {item['version']:item['completed'] for item in store.practice_library(g.user_id)}
        items = position_items([{'version':exercise['version_id'],'exercise':exercise,'completed':saved.get(exercise['version_id'],0)}
                                for exercise in (job['result'] or {}).get('exercises',[])])
        return render_template('beta_job.html',job=job,game=game_metadata(source,color),thumbnail=thumbnail,
                               items=items,practiced=sum(bool(item['completed']) for item in items))

    @app.get('/api/jobs/<jid>')
    def job_status(jid):
        job = store.job(g.user_id,jid)
        return jsonify(status=job['status'], error=job['error'])

    def adapter(version):
        snapshot = store.exercise(g.user_id, version)
        card = card_from_exercise(snapshot)
        g.version_id = version
        # Reuse the existing isolated board view functions in this app's request
        # context. Authentication/security belong to this adapter, chess to web.py.
        return practice_adapter(card, source_label=f"{snapshot.get('origin','human-reviewed')} · source {snapshot['source']['id'][:12]} · version {version[:12]}")

    def identity(version):
        card = card_from_exercise(store.exercise(g.user_id, version))
        return sha256(json.dumps(asdict(card), sort_keys=True).encode()).hexdigest()

    @app.get('/practice/<version>')
    def practice(version):
        return adapter(version).view_functions['practice']()

    def thumbnail_response(board,color):
        content = board_thumbnail(board,color)
        response = Response(content,mimetype='image/svg+xml')
        response.headers['Cache-Control'] = 'private, no-cache'
        response.set_etag(sha256(content.encode()).hexdigest())
        return response.make_conditional(request)

    @app.get('/games/<gid>/thumbnail.svg')
    def game_thumbnail(gid):
        game = store.game(g.user_id,gid)
        return thumbnail_response(validated_game(game['pgn']).end().board(),game['color'])

    @app.get('/practice/<version>/thumbnail.svg')
    def exercise_thumbnail(version):
        card = card_from_exercise(store.exercise(g.user_id,version))
        board = chess.Board(card.position_fen)
        return thumbnail_response(board,'white' if board.turn else 'black')

    @app.route('/practice/<version>/api/position', methods=['GET','POST'])
    def position(version):
        if request.content_length and request.content_length > 8192:
            abort(413)
        return adapter(version).view_functions['board_position']()

    @app.get('/practice/<version>/api/reveal')
    def reveal(version):
        return adapter(version).view_functions['reveal']()

    @app.post('/practice/<version>/api/engine')
    def exploration_engine(version):
        if request.content_length and request.content_length > 8192:
            abort(413)
        card = card_from_exercise(store.exercise(g.user_id,version))
        data = request.get_json()
        if not isinstance(data,dict) or set(data) != {'card_id','moves'}:
            abort(400,'Expected card_id and moves only')
        card_id = identity(version)
        if data['card_id'] != card_id:abort(409,'This card changed; reload before continuing')
        board, _ = replay_moves(chess.Board(card.position_fen),data['moves'])
        result = terminal_result(board)
        if result is None:
            supervisor = app.extensions.get('supervisor')
            if supervisor is None:abort(503,'Exploration engine is unavailable on this installation')
            try:
                result = supervisor.explore(board.fen(),lambda:store.reserve_exploration(
                    g.user_id,local=app.config['LOCAL_TESTING']))
            except RuntimeError as error:abort(503,str(error))
            if result['fen'] != board.fen():abort(503,'Engine returned a different position')
        return jsonify(card_id=card_id,**result)

    def walkthrough_input(version, keys):
        if request.content_length and request.content_length > 2048:abort(413)
        card = card_from_exercise(store.exercise(g.user_id,version))
        data = request.get_json()
        if not isinstance(data,dict) or set(data) != keys:abort(400,'Unexpected walkthrough fields')
        card_id = identity(version)
        if data['card_id'] != card_id:abort(409,'This card changed; reload before continuing')
        if not isinstance(data['proposed_move_uci'],str):abort(400,'Provide a proposed move')
        board = chess.Board(card.position_fen)
        proposed = chess.Move.from_uci(data['proposed_move_uci'])
        if proposed not in board.legal_moves:abort(400,'Illegal proposed move')
        key = 'walkthrough-evidence:' + walkthrough_digest({'user':g.user_id,'version':version,
              'proposed':proposed.uci(),'engine':app.config['STOCKFISH_PATH'],'protocol':2})
        return card,data,card_id,board,proposed,key

    @app.post('/practice/<version>/api/walkthrough')
    def prepare_walkthrough(version):
        card,data,card_id,board,proposed,key = walkthrough_input(version,{'card_id','proposed_move_uci'})
        evidence = store.cache(key)
        if evidence is None:
            supervisor = app.extensions.get('supervisor')
            if supervisor is None:abort(503,'Walkthrough engine is unavailable. You can keep exploring.')
            recommended = board.parse_san(card.continuation_san[0]).uci()
            try:
                evidence = supervisor.walkthrough(board.fen(),proposed.uci(),recommended,
                    lambda:store.reserve_exploration(g.user_id,local=app.config['LOCAL_TESTING']))
            except RuntimeError as error:abort(503,str(error))
            if evidence.get('initial_fen') != board.fen() or evidence.get('walkthrough_id') != walkthrough_digest(
                {k:v for k,v in evidence.items() if k != 'walkthrough_id'}):
                abort(503,'Walkthrough evidence did not match this position')
            store.cache(key,evidence)
        else:
            store.reserve_exploration(g.user_id,local=app.config['LOCAL_TESTING'])
        return jsonify(card_id=card_id,**evidence)

    @app.post('/practice/<version>/api/walkthrough/commentary')
    def walkthrough_commentary(version):
        _,data,card_id,_,_,key = walkthrough_input(version,{'card_id','proposed_move_uci','walkthrough_id','consent'})
        if data['consent'] is not True:abort(400,'Starting the walkthrough requires positions-only consent')
        evidence = store.cache(key)
        if evidence is None or data['walkthrough_id'] != evidence['walkthrough_id']:
            abort(409,'Prepare this walkthrough before requesting commentary')
        def fallback(reason,message):
            return jsonify(card_id=card_id,walkthrough_id=evidence['walkthrough_id'],available=False,
                           reason=reason,message=message,steps=[])
        if not (app.config['WALKTHROUGH_AI_ENABLED'] or app.config['LOCAL_TESTING']):
            return fallback('quality_gate','AI walkthrough commentary awaits teaching-quality review. Board facts remain available.')
        if not app.config['GROQ_API_KEY']:
            return fallback('configuration','AI commentary is unavailable because no Groq API key is configured.')
        cache_key = 'walkthrough-commentary:' + walkthrough_digest({'version':version,
            'proposed':data['proposed_move_uci'],'evidence':evidence['walkthrough_id'],
            'model':app.config['GROQ_MODEL'],'prompt':'walkthrough-v2'})
        cached = store.cache(cache_key)
        try:
            if cached is None:
                store.reserve_ai(g.user_id)
                cached = coach_walkthrough(evidence,app.config['GROQ_API_KEY'],app.config['GROQ_MODEL'])
                store.cache(cache_key,cached)
            validate_walkthrough(cached,evidence)
        except Conflict:
            return fallback('quota','The daily AI allowance is exhausted. Board facts remain available.')
        except HTTPError as error:
            status = error.code;error.close()
            return fallback('provider_error',f'AI provider returned {status}. Board facts remain available.')
        except (TimeoutError,URLError,OSError):
            return fallback('connection','AI commentary could not connect or timed out. Board facts remain available.')
        except (ValueError,TypeError,KeyError,IndexError):
            return fallback('invalid_response','AI commentary failed its evidence checks. Board facts remain available.')
        return jsonify(card_id=card_id,walkthrough_id=evidence['walkthrough_id'],available=True,steps=cached['steps'])

    @app.post('/practice/<version>/api/coaching')
    def coaching(version):
        snapshot = store.exercise(g.user_id,version)
        card_id = identity(version)
        if not isinstance(request.get_json(), dict) or request.get_json() != {'consent': True}:
            abort(400, 'Explicit positions-only consent required')
        fallback = {'card_id':card_id, 'available':False, 'explanation':snapshot['card']['explanation']}
        def unavailable(reason, message):
            return jsonify(fallback | {'reason':reason, 'message':message})
        if snapshot.get('origin') != 'automatic-engine':
            return unavailable('unsupported', 'AI coaching is unavailable for this exercise type.')
        if not app.config['GROQ_API_KEY']:
            return unavailable('configuration', 'AI coaching is unavailable because the server has no Groq API key configured.')
        key = sha256((version + app.config['GROQ_MODEL'] + ':prompt-v1').encode()).hexdigest()
        cached = store.cache(key)
        if cached is None:
            try:
                store.reserve_ai(g.user_id)
                cached = coach(snapshot,app.config['GROQ_API_KEY'],app.config['GROQ_MODEL'])
                store.cache(key,cached)
            except Conflict:
                return unavailable('quota', 'The application’s daily AI allowance is exhausted. Cached explanations can still be opened.')
            except HTTPError as error:
                status = error.code
                error.close()
                if status == 401:
                    return unavailable('credentials', 'Groq rejected the server’s API key. Check its configuration.')
                if status == 429:
                    return unavailable('provider_quota', 'Groq rate limited this request. Wait before requesting another explanation.')
                if status == 403:
                    return unavailable('provider_rejected', 'Groq blocked this request. Check the server’s provider connection and account access.')
                return unavailable('provider_error', 'Groq could not complete this request. Check the configured model or try later.')
            except TimeoutError:
                return unavailable('timeout', 'AI coaching timed out. You can continue practicing and try later.')
            except (URLError, OSError):
                return unavailable('connection', 'The server could not connect securely to Groq. You can continue practicing.')
            except (ValueError, TypeError, KeyError, IndexError):
                return unavailable('invalid_response', 'The AI explanation failed our response checks and was not shown.')
            except Exception:
                app.logger.error('AI coaching failed unexpectedly')
                return unavailable('unavailable', 'AI coaching is temporarily unavailable.')
        try:
            validate_response(cached,snapshot)
        except ValueError:
            return unavailable('invalid_response', 'The cached AI explanation failed our response checks and was not shown.')
        return jsonify(card_id=card_id, available=True, explanation=cached['explanation'], suggestion=cached['suggestion'])

    @app.post('/practice/<version>/api/attempts')
    def save(version):
        if request.content_length and request.content_length > 32768:
            abort(413)
        data = request.get_json()
        if not isinstance(data,dict) or data.get('version_id') != version:
            abort(400)
        store.save_attempt(g.user_id,data)
        return jsonify(card_id=identity(version), saved=True, url=url_for('attempt_detail',submission=data['submission_id']))

    @app.get('/puzzles')
    def puzzles():
        status = request.args.get('status','all')
        if status not in ('all','remaining','practiced'): status = 'all'
        return render_template('beta_puzzles.html',library=grouped_library(store.practice_library(g.user_id),status),
                               status=status,attempts=store.attempts(g.user_id))

    @app.get('/reflections')
    def reflections():
        return render_template('beta_reflections.html',attempts=store.reflections(g.user_id))

    @app.get('/history')
    def history():
        return render_template('beta_history.html', attempts=store.attempts(g.user_id))

    @app.get('/history/<submission>')
    def attempt_detail(submission):
        attempt = store.attempt(g.user_id,submission)
        card = card_from_exercise(store.exercise(g.user_id,attempt['version']))
        board = chess.Board(card.position_fen)
        proposed = board.san(chess.Move.from_uci(attempt['payload']['proposed_move_uci']))
        return render_template('beta_attempt.html', attempt=attempt, proposed_move_san=proposed)

    @app.post('/history/<submission>/delete')
    def delete(submission):
        if request.form.get('confirm') != 'yes':
            abort(400,'Confirm deletion before continuing')
        store.delete_attempt(g.user_id,submission)
        return redirect(url_for('reflections'))

    @app.template_filter('utcdate')
    def utcdate(value):
        return datetime.fromtimestamp(value,timezone.utc).strftime('%Y-%m-%d %H:%M UTC') if value else 'Unavailable'

    return app
