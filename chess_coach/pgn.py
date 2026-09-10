"""Parse PGN games and reconstruct their main-line positions."""

from io import StringIO

import chess
import chess.pgn


def parse_pgn(pgn_text: str) -> chess.pgn.Game:
    """Parse one PGN game, rejecting missing games and parser-reported errors."""
    pgn_stream = StringIO(pgn_text)
    game = chess.pgn.read_game(pgn_stream)

    if game is None:
        raise ValueError("PGN does not contain a game")

    if game.errors:
        details = "; ".join(str(error) for error in game.errors)
        raise ValueError(f"PGN contains parsing errors: {details}")

    if chess.pgn.read_game(pgn_stream) is not None:
        raise ValueError("PGN must contain exactly one game")

    return game


def board_after_ply(game: chess.pgn.Game, ply_count: int) -> chess.Board:
    """Return a fresh board after applying ply_count main-line moves."""
    moves = list(game.mainline_moves())

    if ply_count < 0 or ply_count > len(moves):
        raise ValueError(f"ply_count must be between 0 and {len(moves)}")

    board = game.board()
    for move in moves[:ply_count]:
        board.push(move)

    return board
