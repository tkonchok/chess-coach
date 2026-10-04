"""Shared bounded engine lifetime for CLI and web analysis."""

import time
import chess.engine
from contextlib import contextmanager
from chess_coach.workflow import analyze_pgn, validated_game

class _BudgetedEngine:
    """Apply a shared wall-clock budget without changing domain comparison code."""

    def __init__(self, engine, seconds):
        self.engine = engine
        self.max_analysis_seconds = seconds
        self.deadline = time.monotonic() + seconds
        self.id = engine.id

    def analyse(self, *args, **kwargs):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Game analysis exceeded its time budget")
        self.engine.timeout = min(30, remaining)
        return self.engine.analyse(*args, **kwargs)


@contextmanager
def engine_session(pgn, color, *, engine_path="stockfish", nodes=100_000, seconds=120):
    validated_game(pgn)  # Reject bad input before creating an external process.
    if color not in ("white", "black") or not 1 <= nodes <= 5_000_000 or not 1 <= seconds <= 600:
        raise ValueError("Choose white/black, 1–5,000,000 nodes and 1–600 seconds")
    engine = chess.engine.SimpleEngine.popen_uci(engine_path, timeout=10)
    try:
        settings = {"Threads": 1, "Hash": 16}
        engine.configure(settings)
        yield _BudgetedEngine(engine, seconds)
    finally:
        # Graceful shutdown is bounded too; close the transport even if quit fails.
        engine.timeout = 5
        try:
            engine.quit()
        finally:
            engine.close()


def run_analysis(pgn, color, *, engine_path="stockfish", nodes=100_000, seconds=120):
    with engine_session(pgn, color, engine_path=engine_path, nodes=nodes, seconds=seconds) as engine:
        report = analyze_pgn(engine, pgn, color, nodes=nodes)
        report["engine"].update(options={"Threads": 1, "Hash": 16},
                                max_analysis_seconds=seconds, executable=engine_path)
        return report
