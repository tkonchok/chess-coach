from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from chess_coach.__main__ import _BudgetedEngine, main, run_analysis


class CliTests(unittest.TestCase):
    def test_engine_is_closed_on_success_and_failure(self):
        for failure in (False, True):
            engine = Mock(id={"name": "Test"})
            engine.analyse.side_effect = RuntimeError("broken")
            with self.subTest(failure=failure), patch(
                "chess_coach.__main__.chess.engine.SimpleEngine.popen_uci", return_value=engine
            ):
                if failure:
                    with self.assertRaisesRegex(RuntimeError, "broken"):
                        run_analysis("1. e4 *", "white")
                else:
                    report = run_analysis("*", "white")
                    self.assertEqual(report["engine"]["options"], {"Threads": 1, "Hash": 16})
                engine.quit.assert_called_once()
                engine.close.assert_called_once()

    def test_close_still_runs_when_quit_fails(self):
        engine = Mock(id={"name": "Test"})
        engine.quit.side_effect = TimeoutError("shutdown timeout")
        with patch("chess_coach.__main__.chess.engine.SimpleEngine.popen_uci", return_value=engine):
            with self.assertRaises(TimeoutError):
                run_analysis("*", "white")
        engine.close.assert_called_once()

    def test_bad_input_is_rejected_before_starting_engine(self):
        with patch("chess_coach.__main__.chess.engine.SimpleEngine.popen_uci") as start:
            with self.assertRaises(ValueError):
                run_analysis("", "white")
            with self.assertRaises(ValueError):
                run_analysis("*", "white", seconds=0)
            start.assert_not_called()

    def test_shared_deadline_stops_before_next_search(self):
        engine = Mock()
        with patch("chess_coach.__main__.time.monotonic", side_effect=[100, 101, 106]):
            budgeted = _BudgetedEngine(engine, 5)
            budgeted.analyse("board", "limit")
            self.assertEqual(engine.timeout, 4)
            with self.assertRaises(TimeoutError):
                budgeted.analyse("board", "limit")
        engine.analyse.assert_called_once()

    def test_existing_outputs_are_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            output.write_text("keep me")
            with redirect_stderr(io.StringIO()), patch("chess_coach.__main__.run_analysis") as analyze:
                status = main(["analyze", "examples/game.pgn", "--color", "white", "--output", str(output)])
            self.assertEqual(status, 1)
            analyze.assert_not_called()
            self.assertEqual(output.read_text(), "keep me")

    def test_engine_failure_does_not_write_partial_report(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            with redirect_stderr(io.StringIO()), patch(
                "chess_coach.__main__.run_analysis", side_effect=RuntimeError("failure")
            ):
                status = main(["analyze", "examples/game.pgn", "--color", "white", "--output", str(output)])
            self.assertEqual(status, 1)
            self.assertFalse(output.exists())

    def test_imported_selection_enters_same_analysis_with_detected_color(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            bundle = directory / "import.json"
            bundle.write_text(json.dumps({
                "schema_version": 1, "username": "learner", "requested_at": 123,
                "games": [{"id": "abc123", "pgn": '[Black "Learner"]\n\n1. e4 e5 *',
                           "color": "black", "url": "https://www.chess.com/game/live/1"}]}))
            with redirect_stdout(io.StringIO()), patch(
                "chess_coach.__main__.run_analysis", return_value={"source": {}, "candidates": []}
            ) as analyze:
                status = main(["analyze-import", str(bundle), "--game", "abc",
                               "--output", str(directory / "report.json")])
            self.assertEqual(status, 0)
            self.assertEqual(analyze.call_args.args[1], "black")
            saved = json.loads((directory / "report.json").read_text())
            self.assertEqual(saved["source"]["import"]["game_id"], "abc123")
