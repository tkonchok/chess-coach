"""Conservative automatic practice preparation, never editorial approval."""

from dataclasses import asdict
from hashlib import sha256
import json

import chess
import chess.engine

from chess_coach.analysis import compare_move
from chess_coach.engine import engine_session
from chess_coach.pgn import board_after_ply
from chess_coach.training import build_training_card
from chess_coach.workflow import analyze_pgn, pgn_digest, validated_game


def digest(payload):
    return sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()


def eligible(comparison):
    return (comparison['best_evaluation']['centipawns'] is not None
            and comparison['played_evaluation']['centipawns'] is not None
            and comparison['evaluation_loss'] >= 150
            and comparison['best_evaluation']['centipawns'] >= -200)


def prepare(engine, pgn, color, *, nodes=100_000):
    """Inspect eight ranked candidates; retain at most three stable comparisons."""
    report = analyze_pgn(engine, pgn, color, nodes=nodes)
    report['engine'].update(options={'Threads': 1, 'Hash': 16},
                            verification_nodes=nodes * 2)
    if isinstance(getattr(engine, 'max_analysis_seconds', None), (int, float)):
        report['engine']['max_analysis_seconds'] = engine.max_analysis_seconds
    game = validated_game(pgn)
    source_moves = list(game.mainline_moves())
    exercises = []
    for candidate in report['candidates'][:8]:
        if not eligible(candidate):
            continue
        board = board_after_ply(game, candidate['source_ply_count'])
        verified = asdict(compare_move(engine, board, source_moves[candidate['source_ply_count']],
                                       nodes=nodes * 2))
        if not eligible(verified) or verified['best_move_san'] != candidate['best_move_san']:
            continue
        roots = [board.parse_san(verified['best_move_san'])]
        lines = engine.analyse(board, chess.engine.Limit(nodes=nodes * 2), multipv=min(3, board.legal_moves.count()),
                               info=chess.engine.INFO_SCORE | chess.engine.INFO_PV)
        if not isinstance(lines, list) or not lines:
            raise RuntimeError('Engine omitted continuation evidence')
        preferred = next((line for line in lines if line.get('pv', [None])[0] == roots[0]), None)
        if preferred is None or lines[0].get('pv', [None])[0] != roots[0]:
            continue  # The recommendation changed while collecting evidence.
        preferred_cp = preferred['score'].pov(board.turn).score()
        if preferred_cp is None or preferred_cp < -200:
            continue
        evidence_lines = []
        for line in lines:
            pv = line.get('pv', [])[:6]
            replay = board.copy()
            sans = []
            for move in pv:
                if move not in replay.legal_moves:
                    raise RuntimeError('Engine supplied an illegal continuation')
                sans.append(replay.san(move))
                replay.push(move)
            if sans:
                evidence_lines.append({'moves': sans, 'centipawns': line['score'].pov(board.turn).score()})
        selected = next(line['moves'] for line in evidence_lines if line['moves'][0] == verified['best_move_san'])
        explanation = (f"At the recorded search budget, {verified['best_move_san']} evaluated at "
                       f"{verified['best_evaluation']['centipawns'] / 100:+.2f}, versus "
                       f"{verified['played_evaluation']['centipawns'] / 100:+.2f} for "
                       f"{verified['played_move_san']}, from your side. "
                       "Explore the illustrative line and the opponent's replies. "
                       "This is not proof of a unique or forced solution.")
        card = build_training_card(game, candidate['source_ply_count'],
                                   continuation_san=selected, explanation=explanation)
        payload = {'schema_version': 2, 'origin': 'automatic-engine', 'source': report['source'],
                   'player_color': color, 'engine': report['engine'],
                   'analysis_created_at': report['created_at'], 'candidate': candidate,
                   'verification': verified, 'lines': evidence_lines, 'card': asdict(card)}
        payload['version_id'] = digest(payload)
        exercises.append(payload)
        if len(exercises) == 3:
            break
    return {'report': report, 'exercises': exercises}


def prepare_game(pgn, color, *, engine_path='stockfish', nodes=100_000, seconds=230):
    game = validated_game(pgn)
    if game.headers.get('Result') not in ('1-0', '0-1', '1/2-1/2'):
        raise ValueError('Only completed games can be analyzed in the beta')
    with engine_session(pgn, color, engine_path=engine_path, nodes=nodes, seconds=seconds) as engine:
        return prepare(engine, pgn, color, nodes=nodes)


def card_from_exercise(snapshot):
    from chess_coach.workflow import card_from_review
    if snapshot.get('schema_version') == 1:
        return card_from_review(snapshot)
    try:
        payload = {k: v for k, v in snapshot.items() if k != 'version_id'}
        if snapshot['schema_version'] != 2 or snapshot['origin'] != 'automatic-engine' or digest(payload) != snapshot['version_id']:
            raise ValueError('Invalid automatic exercise version')
        source = snapshot['source']
        game = validated_game(source['pgn'])
        if source['id'] != pgn_digest(source['pgn']) or source['headers'] != dict(game.headers):
            raise ValueError('Exercise source changed')
        c, v = snapshot['candidate'], snapshot['verification']
        board = board_after_ply(game, c['source_ply_count'])
        played = list(game.mainline_moves())[c['source_ply_count']]
        if (not eligible(c) or not eligible(v) or c['best_move_san'] != v['best_move_san']
                or c['position_fen'] != board.fen() or v['position_fen'] != board.fen()
                or c['played_move_uci'] != played.uci() or v['played_move_san'] != board.san(played)
                or snapshot['player_color'] != ('white' if board.turn else 'black')):
            raise ValueError('Exercise does not match stable source evidence')
        card = build_training_card(game, c['source_ply_count'],
                                   continuation_san=snapshot['card']['continuation_san'],
                                   explanation=snapshot['card']['explanation'])
        if (card.continuation_san[0] != v['best_move_san']
                or json.dumps(asdict(card), sort_keys=True) != json.dumps(snapshot['card'], sort_keys=True)):
            raise ValueError('Exercise card changed')
        return card
    except (KeyError, TypeError, IndexError, AttributeError) as error:
        raise ValueError('Malformed exercise snapshot') from error
