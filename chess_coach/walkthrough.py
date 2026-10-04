"""Paired, bounded engine lines and mechanically derived move facts."""
from hashlib import sha256
import json
import chess
import chess.engine

BUDGETS = ((50_000, .5), (100_000, 1))
VALUES = {chess.PAWN:1, chess.KNIGHT:3, chess.BISHOP:3, chess.ROOK:5, chess.QUEEN:9, chess.KING:0}


def digest(value):
    return sha256(json.dumps(value,sort_keys=True,allow_nan=False).encode()).hexdigest()


def material(board):
    return {name:sum(VALUES[p.piece_type] for p in board.piece_map().values() if p.color == color)
            for name,color in [('white',chess.WHITE),('black',chess.BLACK)]}


def step(board, move, ply):
    if move not in board.legal_moves:raise ValueError('Illegal walkthrough continuation')
    before = board.fen();prior = material(board);san = board.san(move)
    moved = chess.piece_name(board.piece_type_at(move.from_square))
    capture_square = move.to_square
    if board.is_en_passant(move):capture_square += -8 if board.turn else 8
    captured = board.piece_at(capture_square) if board.is_capture(move) else None
    color = board.turn
    facts = [{'id':'move','text':f'{"White" if color else "Black"} moves the {moved} from {chess.square_name(move.from_square)} to {chess.square_name(move.to_square)}.',
              'squares':[chess.square_name(move.from_square),chess.square_name(move.to_square)]}]
    if captured:
        facts.append({'id':'capture','text':f'The {chess.piece_name(captured.piece_type)} on {chess.square_name(capture_square)} is captured.',
                      'squares':[chess.square_name(capture_square)]})
    if move.promotion:
        facts.append({'id':'promotion','text':f'The pawn promotes to a {chess.piece_name(move.promotion)}.',
                      'squares':[chess.square_name(move.to_square)]})
    board.push(move)
    if board.is_check():
        facts.append({'id':'check','text':'The move gives check.','squares':[chess.square_name(board.king(board.turn))]})
    outcome = board.outcome()
    if outcome:facts.append({'id':'outcome','text':f'This position ends the game: {outcome.result()}.','squares':[]})
    for target in sorted(board.attacks(move.to_square)):
        piece = board.piece_at(target)
        if piece and piece.color != color and piece.piece_type != chess.KING:
            facts.append({'id':f'attack-{chess.square_name(target)}',
                          'text':f'The moved piece attacks the opposing {chess.piece_name(piece.piece_type)} on {chess.square_name(target)}; this alone does not establish a forced capture.',
                          'squares':[chess.square_name(move.to_square),chess.square_name(target)]})
    now = material(board)
    changes = {side:now[side]-prior[side] for side in now}
    if any(changes.values()):
        facts.append({'id':'material','text':f'Material change using pawn=1, minor piece=3, rook=5, queen=9: White {changes["white"]:+}, Black {changes["black"]:+}. This is not an engine evaluation.', 'squares':[]})
    fallback = ' '.join(f['text'] for f in facts if f['id'] in ('capture','check','promotion','outcome'))
    fallback_ids = [fact['id'] for fact in facts if fact['id'] in ('capture','check','promotion','outcome')]
    if not fallback:
        attacks = [fact for fact in facts if fact['id'].startswith('attack-')]
        if attacks:
            target = max(attacks,key=lambda fact:VALUES[board.piece_type_at(chess.parse_square(fact['squares'][-1]))])
            square = target['squares'][-1]
            fallback = f'The {chess.piece_name(board.piece_type_at(move.to_square))} now attacks the opposing {chess.piece_name(board.piece_type_at(chess.parse_square(square)))} on {square}. This alone does not establish a forced capture.'
            fallback_ids = [target['id']]
        else:fallback = facts[0]['text'];fallback_ids = ['move']
    return {'ply':ply,'uci':move.uci(),'san':san,'before_fen':before,'after_fen':board.fen(),
            'facts':facts,'fallback':fallback,'fallback_fact_ids':fallback_ids,'material':now,'material_change':changes}


def prepare(engine, fen, proposed, recommended):
    initial = chess.Board(fen)
    if not initial.is_valid():raise ValueError('Invalid walkthrough position')
    roots = [('your',chess.Move.from_uci(proposed))]
    if proposed != recommended:roots.append(('recommended',chess.Move.from_uci(recommended)))
    if any(move not in initial.legal_moves for _,move in roots):raise ValueError('Illegal walkthrough root')
    branches = []
    for branch,root in roots:
        searches = []
        for nodes,seconds in BUDGETS:
            info = engine.analyse(initial,chess.engine.Limit(nodes=nodes,time=seconds),root_moves=[root],
                                  info=chess.engine.INFO_SCORE | chess.engine.INFO_PV | chess.engine.INFO_BASIC)
            pv = info.get('pv',[])[:6]
            if not pv or pv[0] != root:raise ValueError('Engine changed a forced walkthrough root')
            board = initial.copy();steps=[]
            for move in pv:
                if board.is_game_over():break
                steps.append(step(board,move,len(steps)+1))
            score = info['score'].pov(initial.turn)
            searches.append({'nodes_limit':nodes,'seconds_limit':seconds,'nodes':info.get('nodes',0),
                             'depth':info.get('depth',0),'centipawns':score.score(),'mate':score.mate(),
                             'moves':[s['uci'] for s in steps]})
        branches.append({'id':branch,'root_uci':root.uci(),'root_san':initial.san(root),
                         'searches':searches,'steps':steps})
    uncertain = False
    if len(branches) == 2:
        scores = [[b['searches'][i]['centipawns'] for b in branches] for i in range(2)]
        uncertain = any(None in pair for pair in scores) or (scores[0][1]-scores[0][0])*(scores[1][1]-scores[1][0]) <= 0
    value = {'schema_version':1,'initial_fen':fen,'perspective':'white' if initial.turn else 'black',
             'comparison_uncertain':uncertain,'same_move':proposed == recommended,
             'engine':{'id':dict(engine.id),'threads':1,'hash_mb':16},'branches':branches}
    value['walkthrough_id'] = digest(value)
    return value


def analyze_walkthrough(fen, proposed, recommended, engine_path):
    engine = chess.engine.SimpleEngine.popen_uci(engine_path,timeout=2)
    try:
        engine.configure({'Threads':1,'Hash':16})
        return prepare(engine,fen,proposed,recommended)
    finally:
        engine.timeout = 1
        try:engine.quit()
        finally:engine.close()
