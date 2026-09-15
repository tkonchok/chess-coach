import unittest

import chess

from chess_coach.pgn import parse_pgn
from chess_coach.training import build_training_card


class BuildTrainingCardTests(unittest.TestCase):
    def setUp(self):
        self.game = parse_pgn("1. e4 e5 2. Nf3 Nc6 *")

    def test_preserves_pre_move_position_and_actual_played_move(self):
        card = build_training_card(
            self.game, 0,
            continuation_san=["d4", "d5", "c4"],
            explanation="Another way to contest the center.",
        )

        self.assertEqual(card.position_fen, chess.STARTING_FEN)
        self.assertEqual(card.source_ply_count, 0)
        self.assertEqual(card.played_move_san, "e4")
        self.assertEqual(card.continuation_san, ("d4", "d5", "c4"))
        self.assertIn("White", card.prompt)
        self.assertNotIn("d4", card.prompt)
        self.assertEqual(card.explanation, "Another way to contest the center.")

    def test_supports_black_and_keeps_original_game_unchanged(self):
        original = str(self.game)
        board = chess.Board()
        board.push_san("e4")
        card = build_training_card(
            self.game, 1,
            continuation_san=["c5", "Nf3"],
            explanation="Black contests d4 with the c-pawn.",
        )

        self.assertEqual(card.position_fen, board.fen())
        self.assertEqual(card.played_move_san, "e5")
        self.assertIn("Black", card.prompt)
        self.assertEqual(str(self.game), original)

    def test_copies_continuation_into_immutable_tuple(self):
        moves = ["d4", "d5"]
        card = build_training_card(
            self.game, 0, continuation_san=moves, explanation="Contest the center."
        )
        moves.append("c4")
        self.assertEqual(card.continuation_san, ("d4", "d5"))

    def test_rejects_illegal_or_invalid_continuation_at_any_step(self):
        for moves in (["e5"], ["d4", "d5", "e5"], ["nonsense"], ["--"]):
            with self.subTest(moves=moves):
                with self.assertRaises(ValueError):
                    build_training_card(
                        self.game, 0,
                        continuation_san=moves,
                        explanation="An illustrative continuation.",
                    )

    def test_requires_a_position_before_an_actual_game_move(self):
        for ply in (-1, 4, 5):
            with self.subTest(ply=ply):
                with self.assertRaises(ValueError):
                    build_training_card(
                        self.game, ply,
                        continuation_san=["d4"], explanation="Contest the center.",
                    )

    def test_rejects_empty_game(self):
        with self.assertRaises(ValueError):
            build_training_card(
                parse_pgn("*"), 0,
                continuation_san=["d4"], explanation="Contest the center.",
            )

    def test_requires_a_continuation_and_explanation(self):
        for moves, explanation in (([], "A lesson."), (["d4"], "  ")):
            with self.subTest(moves=moves, explanation=explanation):
                with self.assertRaises(ValueError):
                    build_training_card(
                        self.game, 0,
                        continuation_san=moves, explanation=explanation,
                    )
