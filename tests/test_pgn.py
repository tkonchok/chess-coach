import unittest

import chess
import chess.pgn

from chess_coach.pgn import board_after_ply, parse_pgn


SAMPLE_PGN = """\
[Event "Milestone 3 fixture"]
[Site "?"]
[Date "2026.09.08"]
[Round "?"]
[White "White"]
[Black "Black"]
[Result "*"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 *
"""

CHESS_COM_PGN = """\
[Event "Live Chess"]
[Site "Chess.com"]
[Date "2026.09.03"]
[Round "-"]
[White "Anonymized White"]
[Black "Anonymized Black"]
[Result "1-0"]
[WhiteElo "1542"]
[BlackElo "1539"]
[TimeControl "600"]
[EndTime "4:08:44 GMT+0000"]
[Termination "Anonymized White won by resignation"]

1. c4 e5 2. Nc3 d6 3. f4 exf4 4. d4 Nf6 5. Bxf4 Be7 6. e3 O-O 7. h3 c6 8. Nf3 h6
9. Bd3 d5 10. cxd5 Nxd5 11. Nxd5 Qxd5 12. O-O g5 13. Bh2 Re8 14. b3 Bb4 15. Bc4
Qe4 16. Ne5 Qxe3+ 17. Kh1 Rxe5 18. Bxf7+ Kg7 19. Bxe5+ Kh7 20. Qc2+ 1-0
"""

class ParsePgnTests(unittest.TestCase):
    def test_parses_one_game_and_preserves_headers(self):
        game = parse_pgn(SAMPLE_PGN)

        self.assertIsInstance(game, chess.pgn.Game)
        self.assertEqual(game.headers["Event"], "Milestone 3 fixture")

    def test_rejects_empty_pgn(self):
        with self.assertRaises(ValueError):
            parse_pgn("")

    def test_rejects_illegal_move_reported_by_parser(self):
        with self.assertLogs("chess.pgn", level="ERROR"):
            with self.assertRaises(ValueError):
                parse_pgn("1. e4 e5 2. e5 *")

    def test_rejects_multiple_games(self):
        with self.assertRaises(ValueError):
            parse_pgn(f"{SAMPLE_PGN}\n{SAMPLE_PGN}")


class BoardAfterPlyTests(unittest.TestCase):
    def setUp(self):
        self.game = parse_pgn(SAMPLE_PGN)

    def test_zero_plies_returns_starting_position(self):
        board = board_after_ply(self.game, 0)

        self.assertEqual(board.fen(), chess.STARTING_FEN)

    def test_three_plies_returns_middle_position(self):
        board = board_after_ply(self.game, 3)

        self.assertEqual(
            board.fen(),
            "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/"
            "RNBQKB1R b KQkq - 1 2",
        )

    def test_all_plies_returns_final_position(self):
        board = board_after_ply(self.game, 6)

        self.assertEqual(
            board.fen(),
            "r1bqkbnr/1ppp1ppp/p1n5/1B2p3/4P3/5N2/PPPP1PPP/"
            "RNBQK2R w KQkq - 0 4",
        )

    def test_rejects_negative_ply_count(self):
        with self.assertRaises(ValueError):
            board_after_ply(self.game, -1)

    def test_rejects_ply_count_beyond_game(self):
        with self.assertRaises(ValueError):
            board_after_ply(self.game, 7)

    def test_ignores_variations(self):
        game = parse_pgn("1. e4 e5 (1... c5) 2. Nf3 *")

        board = board_after_ply(game, 2)

        self.assertEqual(
            board.fen(),
            "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/"
            "RNBQKBNR w KQkq - 0 2",
        )

    def test_each_call_returns_a_fresh_board(self):
        first_board = board_after_ply(self.game, 0)
        second_board = board_after_ply(self.game, 0)

        first_board.push_san("e4")

        self.assertEqual(second_board.fen(), chess.STARTING_FEN)

    def test_returns_position_after_three_plies_from_chess_com_pgn(self):
        game = parse_pgn(CHESS_COM_PGN)

        board = board_after_ply(game, 3)

        self.assertEqual(
            board.fen(),
            "rnbqkbnr/pppp1ppp/8/4p3/2P5/2N5/PP1PPPPP/"
            "R1BQKBNR b KQkq - 1 2",
        )

if __name__ == "__main__":
    unittest.main()
