import copy
import unittest
from unittest.mock import Mock, patch

import chess

from chess_coach.analysis import EngineEvaluation, MoveComparison
from chess_coach.pgn import board_after_ply, parse_pgn
from chess_coach.workflow import analyze_pgn, review_candidate


PGN = '[White "Learner"]\n[Black "Opponent"]\n\n1. e4 e5 2. Nf3 Nc6 *'


def comparison(ply, loss):
    game = parse_pgn(PGN)
    board = board_after_ply(game, ply)
    san = board.san(list(game.mainline_moves())[ply])
    return MoveComparison(board.fen(), san, san,
                          EngineEvaluation(loss, None, loss),
                          EngineEvaluation(0, None, 0), loss)


class WorkflowTests(unittest.TestCase):
    def report(self):
        engine = Mock(id={"name": "Test engine"})
        with patch("chess_coach.workflow.analyze_player_moves",
                   return_value=[comparison(2, 20), comparison(0, 0)]) as analyze:
            report = analyze_pgn(engine, PGN, "white", nodes=123)
        analyze.assert_called_once()
        self.assertEqual(analyze.call_args.kwargs, {"nodes": 123})
        return report

    def test_report_retains_source_ply_ranking_and_engine_settings(self):
        report = self.report()
        self.assertEqual(report["source"]["pgn"], PGN)
        self.assertEqual(report["source"]["headers"]["White"], "Learner")
        self.assertEqual(report["engine"]["id"]["name"], "Test engine")
        self.assertEqual(report["engine"]["nodes_per_search"], 123)
        self.assertEqual([c["source_ply_count"] for c in report["candidates"]], [2, 0])
        self.assertEqual(report["candidates"][0]["played_move_uci"], "g1f3")

    def test_accept_builds_legal_card_and_preserves_review_and_report(self):
        report = self.report()
        original = copy.deepcopy(report)
        review = {"decision": "accept", "source_ply_count": 2,
                  "reason": "A simple development example.",
                  "continuation_san": ["Nf3", "Nc6"],
                  "explanation": "Develop while contesting the center; one example.",
                  "alternatives": "Other developing moves may be reasonable."}
        result = review_candidate(report, review)
        self.assertEqual(result["card"]["source_ply_count"], 2)
        self.assertEqual(result["review"], review)
        self.assertEqual(result["source"], report["source"])
        self.assertEqual(result["engine"], report["engine"])
        self.assertEqual(report, original)

    def test_rejection_requires_reason_but_not_a_card(self):
        result = review_candidate(self.report(), {
            "decision": "reject", "source_ply_count": 2,
            "reason": "No clear lesson beyond ordinary development."})
        self.assertIsNone(result["card"])
        self.assertEqual(result["review"]["decision"], "reject")

    def test_rejects_invalid_review_and_illegal_line(self):
        base = {"decision": "accept", "source_ply_count": 2,
                "reason": "Development", "alternatives": "Bc4 merits review.",
                "continuation_san": ["Nf3"], "explanation": "Develop."}
        for changes in ({"reason": " "}, {"source_ply_count": 1},
                        {"continuation_san": ["e5"]}, {"alternatives": ""},
                        {"decision": "automatic"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                review_candidate(self.report(), base | changes)

    def test_rejects_changed_pgn_or_position_in_saved_report(self):
        for field in ("pgn", "fen", "move"):
            report = self.report()
            if field == "pgn":
                report["source"]["pgn"] += " "
            elif field == "fen":
                report["candidates"][0]["position_fen"] = chess.STARTING_FEN
            else:
                report["candidates"][0]["played_move_san"] = "Bc4"
            with self.subTest(field=field), self.assertRaises(ValueError):
                review_candidate(report, {"decision": "reject", "source_ply_count": 2,
                                          "reason": "Skip."})

    def test_invalid_input_does_not_start_analysis(self):
        with patch("chess_coach.workflow.analyze_player_moves") as analyze:
            for pgn, color, nodes in (("", "white", 10), (PGN, "both", 10),
                                      (PGN, "white", 0)):
                with self.subTest(color=color, nodes=nodes), self.assertRaises(ValueError):
                    analyze_pgn(Mock(), pgn, color, nodes=nodes)
            analyze.assert_not_called()

    def test_empty_candidates_are_not_a_fabricated_exercise(self):
        engine = Mock(id={"name": "Test"})
        result = analyze_pgn(engine, "*", "white")
        self.assertEqual(result["candidates"], [])
        engine.analyse.assert_not_called()

    def test_engine_failures_propagate(self):
        with patch("chess_coach.workflow.analyze_player_moves",
                   side_effect=RuntimeError("engine failed")):
            with self.assertRaisesRegex(RuntimeError, "engine failed"):
                analyze_pgn(Mock(), PGN, "black")
