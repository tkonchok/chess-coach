"""Build practice-and-reveal cards from explicitly selected game positions."""

from collections.abc import Sequence
from dataclasses import dataclass

import chess
import chess.pgn

from chess_coach.pgn import board_after_ply


@dataclass(frozen=True)
class TrainingCard:
    """A prompt and reviewed example line, without automatic answer grading."""

    source_ply_count: int
    position_fen: str
    played_move_san: str
    prompt: str
    continuation_san: tuple[str, ...]
    explanation: str


def build_training_card(
    game: chess.pgn.Game,
    ply_count: int,
    *,
    continuation_san: Sequence[str],
    explanation: str,
) -> TrainingCard:
    """Build a card before a played move, checking each continuation move.

    The caller selects the position and supplies the reviewed line and lesson.
    Legal replay does not prove that the line is forced, best, or unique.
    The input game is unchanged; the returned continuation is an immutable copy.
    """
    moves = list(game.mainline_moves())
    if ply_count < 0 or ply_count >= len(moves):
        raise ValueError("ply_count must identify a position before a game move")
    if not continuation_san:
        raise ValueError("A training card requires a continuation")
    if not explanation.strip():
        raise ValueError("A training card requires an explanation")

    board = board_after_ply(game, ply_count)
    position_fen = board.fen()
    played_move_san = board.san(moves[ply_count])
    player = "White" if board.turn == chess.WHITE else "Black"

    canonical_moves = []
    for index, san in enumerate(continuation_san):
        try:
            move = board.parse_san(san)
            # parse_san also accepts null moves, which aren't legal game moves.
            if move not in board.legal_moves:
                raise ValueError("Move is not legal")
        except ValueError as error:
            raise ValueError(
                f"Invalid continuation at ply {index + 1}: {san!r}"
            ) from error
        canonical_moves.append(board.san(move))
        board.push(move)

    return TrainingCard(
        source_ply_count=ply_count,
        position_fen=position_fen,
        played_move_san=played_move_san,
        prompt=f"{player} to move. Choose a move and explain your idea before revealing the example.",
        continuation_san=tuple(canonical_moves),
        explanation=explanation.strip(),
    )
