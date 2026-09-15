"""Render a training card as a self-contained, offline HTML page."""

from html import escape
from pathlib import Path
from string import Template

import chess
import chess.svg

from chess_coach.training import TrainingCard


def render_training_card(card: TrainingCard, *, source_label: str = "") -> str:
    """Precompute board frames; the browser only controls reveal and navigation.

    Text is escaped before insertion into HTML. Only SVG created locally by
    python-chess is inserted as markup. Reveal content is in the file, so this
    is a practice interface, not a mechanism for securing hidden answers.
    """
    board = chess.Board(card.position_fen)
    orientation = board.turn
    frames = []
    last_move = None
    step_label = "Starting position"

    for step in range(len(card.continuation_san) + 1):
        if step:
            move = board.parse_san(card.continuation_san[step - 1])
            if move not in board.legal_moves:
                raise ValueError("Card continuation contains an illegal move")
            prefix = f"{board.fullmove_number}." if board.turn else f"{board.fullmove_number}..."
            step_label = f"{prefix} {board.san(move)}"
            board.push(move)
            last_move = move

        svg = chess.svg.board(
            board, orientation=orientation, lastmove=last_move,
            check=board.king(board.turn) if board.is_check() else None,
            colors={"square light": "#e9e2d4", "square dark": "#6d8776",
                    "margin": "#243c35", "coord light": "#e9e2d4",
                    "coord dark": "#e9e2d4"},
        )
        # Each inline SVG needs its own piece IDs and matching local references.
        svg = svg.replace('id="', f'id="frame-{step}-')
        svg = svg.replace('href="#', f'href="#frame-{step}-')
        hidden = " hidden" if step else ""
        side = "White" if board.turn else "Black"
        context = f"{side} to move · Move {board.fullmove_number}"
        frames.append(
            f'<div class="board-frame" data-fen="{escape(board.fen())}" '
            f'data-context="{escape(context)}" '
            f'data-label="{escape(step_label)}" role="img" '
            f'aria-label="Chessboard: {escape(step_label)}"{hidden}>{svg}</div>'
        )

    initial = chess.Board(card.position_fen)
    # Board.variation_san formats full move numbers for the revealed line.
    replay = initial.copy()
    moves = []
    for san in card.continuation_san:
        move = replay.parse_san(san)
        moves.append(move)
        replay.push(move)

    template = Template(
        Path(__file__).with_name("templates").joinpath("card.html").read_text(encoding="utf-8")
    )
    return template.substitute(
        player="White" if orientation else "Black",
        orientation="white" if orientation else "black",
        move_number=initial.fullmove_number,
        prompt=escape(card.prompt),
        frames="\n".join(frames),
        continuation=escape(initial.variation_san(moves)),
        explanation=escape(card.explanation),
        played_move=escape(card.played_move_san),
        next_disabled="" if moves else "disabled",
        source_label=escape(source_label),
    )
