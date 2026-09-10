import unittest

import chess
import chess.engine

from chess_coach.analysis import EngineEvaluation, compare_move


class FakeEngine:
    def __init__(self, results):
        self.results = iter(results)
        self.calls = []

    def analyse(self, board, limit, **kwargs):
        self.calls.append((board, limit, kwargs))
        return next(self.results)


def engine_result(score, relative_to, move):
    return {
        "score": chess.engine.PovScore(score, relative_to),
        "pv": [move],
    }


class EngineEvaluationTests(unittest.TestCase):
    def test_requires_exactly_one_score_representation(self):
        invalid_values = (
            {"centipawns": None, "mate_in": None, "ranking_value": 0},
            {"centipawns": 30, "mate_in": 2, "ranking_value": 30},
        )

        for values in invalid_values:
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    EngineEvaluation(**values)

    def test_requires_ranking_value_to_match_centipawn_score(self):
        with self.assertRaises(ValueError):
            EngineEvaluation(centipawns=30, mate_in=None, ranking_value=31)

    def test_requires_ranking_value_to_match_mate_mapping(self):
        with self.assertRaises(ValueError):
            EngineEvaluation(centipawns=None, mate_in=2, ranking_value=99_997)


class CompareMoveTests(unittest.TestCase):
    def setUp(self):
        self.board = chess.Board()
        self.best_move = chess.Move.from_uci("d2d4")
        self.played_move = chess.Move.from_uci("e2e4")

    def test_compares_best_and_played_move_from_movers_perspective(self):
        engine = FakeEngine(
            [
                engine_result(chess.engine.Cp(80), chess.WHITE, self.best_move),
                [
                    engine_result(
                        chess.engine.Cp(-120), chess.WHITE, self.played_move
                    ),
                    engine_result(chess.engine.Cp(80), chess.WHITE, self.best_move),
                ],
            ]
        )

        comparison = compare_move(engine, self.board, self.played_move)

        self.assertEqual(comparison.position_fen, chess.STARTING_FEN)
        self.assertEqual(comparison.played_move_san, "e4")
        self.assertEqual(comparison.best_move_san, "d4")
        self.assertEqual(
            comparison.best_evaluation,
            EngineEvaluation(centipawns=80, mate_in=None, ranking_value=80),
        )
        self.assertEqual(
            comparison.played_evaluation,
            EngineEvaluation(centipawns=-120, mate_in=None, ranking_value=-120),
        )
        self.assertEqual(comparison.evaluation_loss, 200)

    def test_normalizes_scores_for_black_to_move(self):
        self.board.push_san("e4")
        best_move = chess.Move.from_uci("e7e5")
        played_move = chess.Move.from_uci("c7c5")
        engine = FakeEngine(
            [
                engine_result(chess.engine.Cp(70), chess.BLACK, best_move),
                [
                    engine_result(chess.engine.Cp(20), chess.BLACK, played_move),
                    engine_result(chess.engine.Cp(70), chess.BLACK, best_move),
                ],
            ]
        )

        comparison = compare_move(engine, self.board, played_move)

        self.assertEqual(comparison.best_evaluation.centipawns, 70)
        self.assertEqual(comparison.played_evaluation.centipawns, 20)
        self.assertEqual(comparison.evaluation_loss, 50)

    def test_compares_seeded_best_and_played_move_in_one_paired_search(self):
        engine = FakeEngine(
            [
                engine_result(chess.engine.Cp(30), chess.WHITE, self.best_move),
                [
                    engine_result(chess.engine.Cp(30), chess.WHITE, self.best_move),
                    engine_result(chess.engine.Cp(20), chess.WHITE, self.played_move),
                ],
            ]
        )

        compare_move(engine, self.board, self.played_move, nodes=50_000)

        self.assertEqual(len(engine.calls), 2)
        self.assertNotIn("root_moves", engine.calls[0][2])
        self.assertNotIn("multipv", engine.calls[0][2])
        self.assertEqual(
            engine.calls[1][2]["root_moves"], [self.best_move, self.played_move]
        )
        self.assertEqual(engine.calls[1][2]["multipv"], 2)
        self.assertEqual(engine.calls[0][1].nodes, 50_000)
        self.assertEqual(engine.calls[1][1].nodes, 50_000)

    def test_uses_one_search_when_played_move_is_seeded_best(self):
        engine = FakeEngine(
            [engine_result(chess.engine.Cp(40), chess.WHITE, self.played_move)]
        )

        comparison = compare_move(engine, self.board, self.played_move)

        self.assertEqual(len(engine.calls), 1)
        self.assertEqual(comparison.best_move_san, "e4")
        self.assertEqual(comparison.best_evaluation.centipawns, 40)
        self.assertEqual(comparison.played_evaluation.centipawns, 40)
        self.assertEqual(comparison.evaluation_loss, 0)

    def test_uses_played_move_as_best_when_paired_score_is_higher(self):
        engine = FakeEngine(
            [
                engine_result(chess.engine.Cp(50), chess.WHITE, self.best_move),
                [
                    engine_result(chess.engine.Cp(50), chess.WHITE, self.best_move),
                    engine_result(chess.engine.Cp(60), chess.WHITE, self.played_move),
                ],
            ]
        )

        comparison = compare_move(engine, self.board, self.played_move)

        self.assertEqual(comparison.best_move_san, "e4")
        self.assertEqual(comparison.best_evaluation.centipawns, 60)
        self.assertEqual(comparison.played_evaluation.centipawns, 60)
        self.assertEqual(comparison.evaluation_loss, 0)

    def test_does_not_mutate_input_board(self):
        engine = FakeEngine(
            [
                engine_result(chess.engine.Cp(30), chess.WHITE, self.best_move),
                [
                    engine_result(chess.engine.Cp(30), chess.WHITE, self.best_move),
                    engine_result(chess.engine.Cp(20), chess.WHITE, self.played_move),
                ],
            ]
        )
        original_fen = self.board.fen()
        original_stack = list(self.board.move_stack)

        compare_move(engine, self.board, self.played_move)

        self.assertEqual(self.board.fen(), original_fen)
        self.assertEqual(self.board.move_stack, original_stack)

    def test_preserves_mate_information_and_provides_a_ranking_value(self):
        engine = FakeEngine(
            [
                engine_result(chess.engine.Mate(2), chess.WHITE, self.best_move),
                [
                    engine_result(
                        chess.engine.Mate(2), chess.WHITE, self.best_move
                    ),
                    engine_result(chess.engine.Cp(0), chess.WHITE, self.played_move),
                ],
            ]
        )

        comparison = compare_move(engine, self.board, self.played_move)

        self.assertEqual(
            comparison.best_evaluation,
            EngineEvaluation(centipawns=None, mate_in=2, ranking_value=99_998),
        )
        self.assertEqual(
            comparison.played_evaluation,
            EngineEvaluation(centipawns=0, mate_in=None, ranking_value=0),
        )
        self.assertEqual(comparison.evaluation_loss, 99_998)

    def test_rejects_non_positive_node_limit(self):
        for nodes in (0, -1):
            with self.subTest(nodes=nodes):
                engine = FakeEngine([])

                with self.assertRaises(ValueError):
                    compare_move(engine, self.board, self.played_move, nodes=nodes)

                self.assertEqual(engine.calls, [])

    def test_rejects_illegal_played_move(self):
        engine = FakeEngine([])
        illegal_move = chess.Move.from_uci("e2e5")

        with self.assertRaises(ValueError):
            compare_move(engine, self.board, illegal_move)

        self.assertEqual(engine.calls, [])

    def test_rejects_missing_engine_score(self):
        engine = FakeEngine([{"pv": [self.best_move]}])

        with self.assertRaises(RuntimeError):
            compare_move(engine, self.board, self.played_move)

    def test_rejects_missing_principal_variation(self):
        engine = FakeEngine(
            [{"score": chess.engine.PovScore(chess.engine.Cp(30), chess.WHITE)}]
        )

        with self.assertRaises(RuntimeError):
            compare_move(engine, self.board, self.played_move)

    def test_rejects_missing_root_in_paired_results(self):
        engine = FakeEngine(
            [
                engine_result(chess.engine.Cp(30), chess.WHITE, self.best_move),
                [engine_result(chess.engine.Cp(30), chess.WHITE, self.best_move)],
            ]
        )

        with self.assertRaises(RuntimeError):
            compare_move(engine, self.board, self.played_move)

    def test_rejects_duplicate_root_in_paired_results(self):
        engine = FakeEngine(
            [
                engine_result(chess.engine.Cp(30), chess.WHITE, self.best_move),
                [
                    engine_result(chess.engine.Cp(30), chess.WHITE, self.best_move),
                    engine_result(chess.engine.Cp(25), chess.WHITE, self.best_move),
                ],
            ]
        )

        with self.assertRaises(RuntimeError):
            compare_move(engine, self.board, self.played_move)

    def test_rejects_unexpected_root_in_paired_results(self):
        unexpected_move = chess.Move.from_uci("c2c4")
        engine = FakeEngine(
            [
                engine_result(chess.engine.Cp(30), chess.WHITE, self.best_move),
                [
                    engine_result(chess.engine.Cp(30), chess.WHITE, self.best_move),
                    engine_result(chess.engine.Cp(25), chess.WHITE, unexpected_move),
                ],
            ]
        )

        with self.assertRaises(RuntimeError):
            compare_move(engine, self.board, self.played_move)


if __name__ == "__main__":
    unittest.main()
