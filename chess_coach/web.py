"""A local-only practice adapter. No engine, accounts, or durable attempt storage.

The browser sends a move path, never an arbitrary FEN. Each request replays that
path from the immutable card so tabs cannot change each other's board state.
"""

from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
from xml.etree import ElementTree

import chess
import chess.svg
from flask import Flask, jsonify, render_template, request
from markupsafe import Markup
from werkzeug.exceptions import HTTPException

from chess_coach.pgn import parse_pgn
from chess_coach.training import TrainingCard, build_training_card
from chess_coach.workflow import card_from_review
from chess_coach.live import replay_moves


def piece_svg(symbol):
    """Convert trusted SVG colors to attributes compatible with our CSP."""
    root = ElementTree.fromstring(chess.svg.piece(chess.Piece.from_symbol(symbol)))
    for element in root.iter():
        element.attrib.pop('id', None)
        style = element.attrib.pop('style', '')
        for declaration in style.split(';'):
            if declaration.strip():
                name, value = declaration.split(':', 1)
                element.set(name.strip(), value.strip())
    # HTML's SVG parser recognizes unprefixed elements and their namespace.
    for element in root.iter():
        element.tag = element.tag.removeprefix('{http://www.w3.org/2000/svg}')
    root.set('xmlns', 'http://www.w3.org/2000/svg')
    return Markup(ElementTree.tostring(root, encoding='unicode'))


MAX_EXPLORATION_PLIES = 128
MAX_REVIEW_BYTES = 25_000_000  # Match the CLI's JSON-file limit, not move-request size.


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
        board, sans = replay_moves(initial, moves)
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
            symbol: piece_svg(symbol)
            for symbol in "PNBRQKpnbrqk"
        }
        return render_template("practice.html", card_id=card_id, source_label=source_label,
                               played_move_san=card.played_move_san, original_move_number=card.source_ply_count // 2 + 1,
                               orientation="white" if initial.turn else "black", pieces=pieces,
                               board_files=list('abcdefgh' if initial.turn else 'hgfedcba'),
                               board_ranks=list(range(8, 0, -1) if initial.turn else range(1, 9)),
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


def create_app_from_review(review_path: str) -> Flask:
    """Load a bounded UTF-8 review file; fail rather than use a fallback card."""
    # One extra byte distinguishes an exactly-at-limit file from a larger one.
    with open(review_path, "rb") as handle:
        content = handle.read(MAX_REVIEW_BYTES + 1)
    if len(content) > MAX_REVIEW_BYTES:
        raise ValueError(f"Review file exceeds {MAX_REVIEW_BYTES:,} bytes: {review_path}")

    snapshot = json.loads(content.decode("utf-8"))
    card = card_from_review(snapshot)
    source = snapshot["source"]
    headers = source["headers"]
    source_label = (
        f"{headers.get('White', 'Unknown')} vs {headers.get('Black', 'Unknown')} · "
        f"{headers.get('Date', 'Unknown')} · ply {card.source_ply_count} · "
        f"source {source['id'][:12]} · review {snapshot['version_id'][:12]}"
    )
    return create_app(card, source_label=source_label)
