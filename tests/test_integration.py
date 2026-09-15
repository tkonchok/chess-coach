"""Opt-in real-engine workflow checks; never assert exact Stockfish scores."""

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import tempfile
import unittest

from chess_coach.__main__ import main
from chess_coach.pgn import board_after_ply, parse_pgn


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.environ.get("RUN_STOCKFISH_TESTS") == "1", "Set RUN_STOCKFISH_TESTS=1 for real-engine checks")
class RealWorkflowTests(unittest.TestCase):
    def test_two_games_produce_traceable_legally_replayable_cards(self):
        for pgn_name, review_name, color in (
            ("game.pgn", "first-review.json", "white"),
            ("second-game.pgn", "second-review.json", "black"),
        ):
            with self.subTest(game=pgn_name), tempfile.TemporaryDirectory() as directory:
                directory = Path(directory)
                report_path, card_path = directory / "analysis.json", directory / "card"
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(main([
                        "analyze", str(ROOT / "examples" / pgn_name), "--color", color,
                        "--nodes", "1000", "--output", str(report_path),
                    ]), 0)
                    self.assertEqual(main([
                        "review", str(report_path), str(ROOT / "examples" / review_name),
                        "--output", str(card_path),
                    ]), 0)
                report = json.loads(report_path.read_text())
                reviewed = json.loads((card_path / "review.json").read_text())
                self.assertEqual(reviewed["source"], report["source"])
                card = reviewed["card"]
                board = board_after_ply(parse_pgn(report["source"]["pgn"]), card["source_ply_count"])
                self.assertEqual(board.fen(), card["position_fen"])
                for san in card["continuation_san"]:
                    move = board.parse_san(san)
                    self.assertIn(move, board.legal_moves)
                    board.push(move)
                self.assertIn(reviewed["version_id"][:12], (card_path / "card.html").read_text())
