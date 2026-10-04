"""Bounded exploratory evaluation, always from White's perspective."""
import chess
import chess.engine


def replay_moves(initial, moves):
    if not isinstance(moves, list) or len(moves) > 128:
        raise ValueError('Provide a move list of at most 128 plies')
    board, sans = initial.copy(), []
    for index, uci in enumerate(moves):
        if not isinstance(uci, str) or len(uci) not in (4, 5):
            raise ValueError(f'Invalid move at ply {index + 1}')
        try:
            move = chess.Move.from_uci(uci)
        except ValueError as error:
            raise ValueError(f'Invalid move at ply {index + 1}') from error
        if board.is_game_over() or move not in board.legal_moves:
            raise ValueError(f'Illegal move at ply {index + 1}')
        sans.append(board.san(move))
        board.push(move)
    return board, sans


def terminal_result(board):
    outcome = board.outcome()
    if outcome is None:
        return None
    return {'fen':board.fen(), 'centipawns':None, 'mate':None,
            'terminal':outcome.result(), 'best_move_uci':None, 'best_move_san':None,
            'line':[], 'nodes':0, 'depth':0}


def evaluate(engine, board):
    terminal = terminal_result(board)
    if terminal:
        return terminal
    info = engine.analyse(board, chess.engine.Limit(time=.35, nodes=25_000),
                          info=chess.engine.INFO_SCORE | chess.engine.INFO_PV | chess.engine.INFO_BASIC)
    score = info['score'].pov(chess.WHITE)
    pv = info.get('pv', [])[:6]
    if not pv or pv[0] not in board.legal_moves:
        raise ValueError('Engine omitted a legal recommendation')
    replay, sans = board.copy(), []
    for move in pv:
        if move not in replay.legal_moves:
            raise ValueError('Illegal exploratory engine continuation')
        sans.append(replay.san(move)); replay.push(move)
    return {'fen':board.fen(), 'centipawns':score.score(), 'mate':score.mate(),
            'terminal':None, 'best_move_uci':pv[0].uci(), 'best_move_san':sans[0],
            'line':sans, 'nodes':info.get('nodes',0), 'depth':info.get('depth',0)}


def analyze_position(fen, engine_path):
    board = chess.Board(fen)
    if not board.is_valid():
        raise ValueError('Invalid exploration position')
    engine = chess.engine.SimpleEngine.popen_uci(engine_path, timeout=2)
    try:
        engine.configure({'Threads':1,'Hash':16})
        return evaluate(engine, board)
    finally:
        engine.timeout = 1
        try:engine.quit()
        finally:engine.close()
