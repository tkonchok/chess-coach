"""Connect analysis and editorial review without depending on an interface.

Reports are JSON-compatible snapshots, not a database. The original PGN and its
digest travel with every reviewed decision so it can be checked and replayed.
"""

from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256

import chess

from chess_coach.analysis import analyze_player_moves
from chess_coach.pgn import board_after_ply, parse_pgn
from chess_coach.training import build_training_card


MAX_PGN_BYTES = 1_000_000
MAX_PLIES = 1_000


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def pgn_digest(pgn: str) -> str:
    """Identity of this exact input document, not a universal game identifier."""
    return sha256(pgn.encode("utf-8")).hexdigest()


def validated_game(pgn: str):
    if len(pgn.encode("utf-8")) > MAX_PGN_BYTES:
        raise ValueError("PGN exceeds the 1 MB input limit")
    game = parse_pgn(pgn)
    if game.board().fen() != chess.STARTING_FEN or game.headers.get("Variant", "Standard") != "Standard":
        raise ValueError("Only standard chess from the usual starting position is supported")
    if sum(1 for _ in game.mainline_moves()) > MAX_PLIES:
        raise ValueError("Game exceeds the 1,000-ply limit")
    return game


def analyze_pgn(engine, pgn: str, player_color: str, *, nodes: int = 100_000) -> dict:
    """Return ranked, traceable candidates. The caller owns the engine process."""
    if player_color not in ("white", "black"):
        raise ValueError("Choose player color explicitly: white or black")
    if type(nodes) is not int or nodes <= 0:
        raise ValueError("nodes must be a positive integer")
    game = validated_game(pgn)
    color = player_color == "white"
    # Full FEN includes side and fullmove number, so each source ply has a unique
    # key even when the piece arrangement repeats. Keep the existing analyzer.
    positions = {}
    board = game.board()
    for ply, move in enumerate(game.mainline_moves()):
        if board.turn == color:
            positions[board.fen()] = (ply, move.uci())
        board.push(move)

    candidates = []
    for comparison in analyze_player_moves(engine, game, color, nodes=nodes):
        ply, uci = positions[comparison.position_fen]
        candidates.append(asdict(comparison) | {
            "source_ply_count": ply, "played_move_uci": uci,
        })
    return {
        "schema_version": 1,
        "created_at": utc_now(),
        "source": {"id": pgn_digest(pgn), "pgn": pgn, "headers": dict(game.headers)},
        "player_color": player_color,
        "engine": {"id": dict(engine.id), "nodes_per_search": nodes,
                   "python_chess_version": chess.__version__,
                   "method": "seed-then-paired-multipv-v1",
                   "process_reused_across_moves": True},
        "candidates": candidates,
    }


def review_candidate(report: dict, review: dict) -> dict:
    """Record an explicit acceptance or rejection; never grade a player's move.

    A digest detects accidental source edits; it is not an authenticity signature.
    A reviewed card is a snapshot. Later edits produce a different version ID.
    """
    import json

    try:
        if report["schema_version"] != 1:
            raise ValueError("Unsupported analysis report version")
        source = report["source"]
        if source["id"] != pgn_digest(source["pgn"]):
            raise ValueError("Source PGN no longer matches the analysis report")
        game = validated_game(source["pgn"])
        if source["headers"] != dict(game.headers):
            raise ValueError("Source headers no longer match the PGN")
        decision = review["decision"]
        if decision not in ("accept", "reject"):
            raise ValueError("Review decision must be accept or reject")
        if not isinstance(review["reason"], str) or not review["reason"].strip():
            raise ValueError("Record why this candidate was selected or rejected")
        ply = review["source_ply_count"]
        if type(ply) is not int:
            raise ValueError("source_ply_count must be an integer")
        matches = [c for c in report["candidates"] if c["source_ply_count"] == ply]
        if len(matches) != 1:
            raise ValueError("Choose exactly one candidate ply from this report")
        candidate = matches[0]
        board = board_after_ply(game, ply)
        moves = list(game.mainline_moves())
        if (ply >= len(moves) or candidate["position_fen"] != board.fen()
                or candidate["played_move_san"] != board.san(moves[ply])
                or candidate["played_move_uci"] != moves[ply].uci()
                or report["player_color"] != ("white" if board.turn else "black")):
            raise ValueError("Candidate does not match its source game and player")
        card = None
        if decision == "accept":
            if not isinstance(review["alternatives"], str) or not review["alternatives"].strip():
                raise ValueError("Record the alternative moves considered and any uncertainty")
            line = review["continuation_san"]
            if not isinstance(line, list) or not all(isinstance(san, str) for san in line):
                raise ValueError("continuation_san must be a JSON list of SAN moves")
            card = asdict(build_training_card(
                game, ply, continuation_san=line, explanation=review["explanation"],
            ))
        result = deepcopy({
            "schema_version": 1, "source": source, "player_color": report["player_color"],
            "engine": report["engine"], "analysis_created_at": report["created_at"],
            "candidate": candidate, "review": review, "card": card,
        })
        result["version_id"] = sha256(
            json.dumps(result, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return result
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError(f"Invalid report or review structure: {error}") from error
