import unittest
from unittest.mock import Mock, patch

import chess

from chess_coach.analysis import EngineEvaluation, MoveComparison, analyze_player_moves
from chess_coach.pgn import board_after_ply, parse_pgn


def comparison_fixture(game, ply, loss=0, best_move_san=None):
    """Create a comparison with controlled scores at a real game position."""
    board = board_after_ply(game, ply)
    move = list(game.mainline_moves())[ply]
    played_move_san = board.san(move)
    return MoveComparison(
        position_fen=board.fen(),
        played_move_san=played_move_san,
        best_move_san=best_move_san or played_move_san,
        best_evaluation=EngineEvaluation(loss, None, loss),
        played_evaluation=EngineEvaluation(0, None, 0),
        evaluation_loss=loss,
    )


class AnalyzePlayerMovesTests(unittest.TestCase):
    def test_compares_black_moves_from_the_correct_positions(self):
        game = parse_pgn("1. e4 e5 2. Nf3 Nc6 *")
        observed = []

        first_comparison = comparison_fixture(game, 1)
        second_comparison = comparison_fixture(game, 3)
        fake_results = iter([first_comparison, second_comparison])

        def record_comparison(engine, board, move, **kwargs):
            observed.append((board.san(move), board.fen()))
            return next(fake_results)

        with patch(
            "chess_coach.analysis.compare_move",
            side_effect=record_comparison,
        ):
            results = analyze_player_moves(object(), game, chess.BLACK)

        expected_board = chess.Board()
        expected_board.push_san("e4")
        before_e5 = expected_board.fen()

        expected_board.push_san("e5")
        expected_board.push_san("Nf3")
        before_nc6 = expected_board.fen()

        self.assertEqual(
            observed,
            [("e5", before_e5), ("Nc6", before_nc6)],
        )

        self.assertEqual(results, [first_comparison, second_comparison])

    def test_compares_white_moves_from_the_correct_positions(self):
        game = parse_pgn("1. e4 e5 2. Nf3 Nc6 *")
        observed = []

        first_comparison = comparison_fixture(game, 0)
        second_comparison = comparison_fixture(game, 2)
        fake_results = iter([first_comparison, second_comparison])

        def record_comparison(engine, board, move, **kwargs):
            observed.append((board.san(move), board.fen()))
            return next(fake_results)

        with patch(
            "chess_coach.analysis.compare_move",
            side_effect=record_comparison,
        ):
            results = analyze_player_moves(object(), game, chess.WHITE)

        expected_board = chess.Board()
        before_e4 = expected_board.fen()

        expected_board.push_san("e4")
        expected_board.push_san("e5")
        before_nf3 = expected_board.fen()

        self.assertEqual(
            observed,
            [("e4", before_e4), ("Nf3", before_nf3)],
        )

        self.assertEqual(results, [first_comparison, second_comparison])

    def test_ranks_largest_losses_first_preserving_game_order_for_ties(self):
        game = parse_pgn("1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 *")
        comparisons = [
            comparison_fixture(game, 0, loss=20, best_move_san="d4"),
            comparison_fixture(game, 2, loss=150, best_move_san="Bc4"),
            comparison_fixture(game, 4, loss=60, best_move_san="Bc4"),
            comparison_fixture(game, 6, loss=150, best_move_san="Bxc6"),
        ]

        with patch(
            "chess_coach.analysis.compare_move", side_effect=comparisons
        ):
            results = analyze_player_moves(object(), game, chess.WHITE)

        self.assertEqual(
            results,
            [comparisons[1], comparisons[3], comparisons[2], comparisons[0]],
        )

    def test_passes_node_budget_and_reuses_caller_owned_engine(self):
        game = parse_pgn("1. e4 e5 2. Nf3 Nc6 *")
        engine = Mock()
        calls = []
        comparisons = [comparison_fixture(game, 0), comparison_fixture(game, 2)]
        fake_results = iter(comparisons)

        def record_comparison(received_engine, board, move, *, nodes):
            calls.append((received_engine, nodes, list(board.move_stack)))
            return next(fake_results)

        with patch("chess_coach.analysis.compare_move", side_effect=record_comparison):
            results = analyze_player_moves(engine, game, chess.WHITE, nodes=25_000)

        self.assertEqual(results, comparisons)
        self.assertEqual(len(calls), 2)
        for received_engine, nodes, _ in calls:
            self.assertIs(received_engine, engine)
            self.assertEqual(nodes, 25_000)
        self.assertEqual(calls[0][2], [])
        self.assertEqual(calls[1][2], list(game.mainline_moves())[:2])
        engine.quit.assert_not_called()

    def test_returns_empty_list_when_player_has_no_moves(self):
        for pgn, color in (("*", chess.WHITE), ("1. e4 *", chess.BLACK)):
            with self.subTest(pgn=pgn):
                game = parse_pgn(pgn)
                with patch("chess_coach.analysis.compare_move") as compare:
                    self.assertEqual(analyze_player_moves(object(), game, color), [])
                    compare.assert_not_called()

    def test_rejects_non_positive_nodes_even_for_empty_game(self):
        game = parse_pgn("*")
        for nodes in (0, -1):
            with self.subTest(nodes=nodes):
                with patch("chess_coach.analysis.compare_move") as compare:
                    with self.assertRaises(ValueError):
                        analyze_player_moves(object(), game, chess.WHITE, nodes=nodes)
                    compare.assert_not_called()

    def test_ignores_side_variations(self):
        game = parse_pgn("1. e4 e5 (1... c5) 2. Nf3 Nc6 *")
        observed = []

        def record_comparison(engine, board, move, **kwargs):
            observed.append(board.san(move))
            return comparison_fixture(game, len(board.move_stack))

        with patch("chess_coach.analysis.compare_move", side_effect=record_comparison):
            analyze_player_moves(object(), game, chess.BLACK)

        self.assertEqual(observed, ["e5", "Nc6"])

    def test_propagates_engine_failure_without_returning_partial_results(self):
        game = parse_pgn("1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 *")
        failure = RuntimeError("Engine did not return a score")
        engine = Mock()
        with patch(
            "chess_coach.analysis.compare_move",
            side_effect=[comparison_fixture(game, 0), failure],
        ) as compare:
            with self.assertRaises(RuntimeError) as caught:
                analyze_player_moves(engine, game, chess.WHITE)

        self.assertIs(caught.exception, failure)
        self.assertEqual(compare.call_count, 2)
        engine.quit.assert_not_called()

    def test_preserves_game_headers_comments_and_variations(self):
        game = parse_pgn('1. e4 {A comment} e5 (1... c5) 2. Nf3 *')
        original = str(game)
        comparisons = [comparison_fixture(game, 0), comparison_fixture(game, 2)]
        with patch("chess_coach.analysis.compare_move", side_effect=comparisons):
            analyze_player_moves(object(), game, chess.WHITE)

        self.assertEqual(str(game), original)
