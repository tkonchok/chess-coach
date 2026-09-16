"""A local-only practice adapter. No engine, accounts, or durable attempt storage.

The browser sends a move path, never an arbitrary FEN. Each request replays that
path from the immutable card so tabs cannot change each other's board state.
"""

from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import re

import chess
import chess.svg
from flask import Flask, jsonify, render_template, request
from markupsafe import Markup
from werkzeug.exceptions import HTTPException

from chess_coach.pgn import parse_pgn
from chess_coach.training import TrainingCard, build_training_card


MAX_EXPLORATION_PLIES = 128


def _default_card() -> tuple[TrainingCard, str]:
    examples = Path(__file__).resolve().parents[1] / "examples"
    game = parse_pgn((examples / "game.pgn").read_text(encoding="utf-8"))
    review = json.loads((examples / "first-review.json").read_text(encoding="utf-8"))
    card = build_training_card(game, review["source_ply_count"],
                               continuation_san=review["continuation_san"],
                               explanation=review["explanation"])
    return card, f"{game.headers['White']} vs {game.headers['Black']} · {game.headers['Date']} · ply {card.source_ply_count}"


def create_app(card: TrainingCard | None = None, *, source_label: str = "") -> Flask:
    """Build an isolated app; tests can supply any legally reviewed card."""
    if card is None:
        card, source_label = _default_card()
    initial = chess.Board(card.position_fen)
    if not initial.is_valid():
        raise ValueError("Practice card has an invalid starting position")
    example_board = initial.copy()
    example_moves = []
    for san in card.continuation_san:
        move = example_board.parse_san(san)
        if move not in example_board.legal_moves:
            raise ValueError("Practice card has an illegal example move")
        example_moves.append(move)
        example_board.push(move)
    if not example_moves:
        raise ValueError("Practice card requires a reviewed example")
    card_id = sha256(json.dumps(asdict(card), sort_keys=True).encode()).hexdigest()
    app = Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=8192, TRUSTED_HOSTS=["localhost", "127.0.0.1"])

    def position(moves):
        if not isinstance(moves, list) or len(moves) > MAX_EXPLORATION_PLIES:
            raise ValueError("Provide a move list of at most 128 plies")
        board, sans = initial.copy(), []
        for index, uci in enumerate(moves):
            if not isinstance(uci, str) or len(uci) not in (4, 5):
                raise ValueError(f"Invalid move at ply {index + 1}")
            try:
                move = chess.Move.from_uci(uci)
            except ValueError as error:
                raise ValueError(f"Invalid move at ply {index + 1}") from error
            if board.is_game_over() or move not in board.legal_moves:
                raise ValueError(f"Illegal move at ply {index + 1}")
            sans.append(board.san(move))
            board.push(move)
        outcome = board.outcome()
        return {
            "card_id": card_id, "fen": board.fen(), "sans": sans,
            "pieces": {chess.square_name(square): piece.symbol() for square, piece in board.piece_map().items()},
            "legal_moves": [move.uci() for move in board.legal_moves] if outcome is None else [],
            "turn": "white" if board.turn else "black", "fullmove_number": board.fullmove_number,
            "check": chess.square_name(board.king(board.turn)) if board.is_check() else None,
            "outcome": outcome.result() if outcome else None,
        }

    @app.before_request
    def same_origin():
        origin = request.headers.get("Origin")
        if (request.headers.get("Sec-Fetch-Site") == "cross-site"
                or origin is not None and origin != request.host_url.rstrip("/")):
            return jsonify(error="Cross-origin requests are not supported"), 403

    @app.after_request
    def headers(response):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self'; connect-src 'self'; object-src 'none'; "
            "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.description), error.code

    @app.get("/")
    def practice():
        squares = list(chess.SQUARES)
        squares.sort(key=lambda s: (-chess.square_rank(s), chess.square_file(s)), reverse=not initial.turn)
        # Only locally generated python-chess SVG is trusted markup. All supplied
        # text uses Jinja's normal escaping. The browser clones these piece assets.
        # These self-contained piece SVGs have no ID references. Remove their
        # group IDs so cloning several pawns does not duplicate document IDs.
        pieces = {
            symbol: Markup(re.sub(r' id="[^"]*"', '', chess.svg.piece(chess.Piece.from_symbol(symbol))))
            for symbol in "PNBRQKpnbrqk"
        }
        return render_template("practice.html", card_id=card_id, source_label=source_label,
                               orientation="white" if initial.turn else "black", pieces=pieces,
                               squares=[{"name": chess.square_name(s),
                                         "shade": "dark" if (chess.square_rank(s) + chess.square_file(s)) % 2 == 0 else "light"}
                                        for s in squares])

    @app.route("/api/position", methods=["GET", "POST"])
    def board_position():
        if request.method == "GET":
            return jsonify(position([]))
        data = request.get_json()
        if not isinstance(data, dict) or set(data) != {"card_id", "moves"}:
            return jsonify(error="Expected card_id and moves only"), 400
        if data["card_id"] != card_id:
            return jsonify(error="This card changed. Reload the page before continuing."), 409
        try:
            return jsonify(position(data["moves"]))
        except ValueError as error:
            return jsonify(error=str(error)), 400

    @app.get("/api/reveal")
    def reveal():
        # A UI reveal boundary, not an anti-cheating or authentication mechanism.
        return jsonify(card_id=card_id, moves=[move.uci() for move in example_moves],
                       line=initial.variation_san(example_moves), explanation=card.explanation,
                       played_move_san=card.played_move_san)

    return app
