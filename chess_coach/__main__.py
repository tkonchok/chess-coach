"""Local adapters for import, analysis, and reviewed-card generation."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

import chess.engine

from chess_coach.chesscom import ChessComClient, import_history
from chess_coach.presentation import render_training_card
from chess_coach.training import TrainingCard
from chess_coach.workflow import MAX_PGN_BYTES, analyze_pgn, review_candidate, validated_game


MAX_JSON_BYTES = 25_000_000


def read_text(path, limit):
    with Path(path).open("rb") as handle:
        content = handle.read(limit + 1)
    if len(content) > limit:
        raise ValueError(f"Input exceeds {limit:,} bytes: {path}")
    return content.decode("utf-8")


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


class _BudgetedEngine:
    """Apply a shared wall-clock budget without changing domain comparison code."""

    def __init__(self, engine, seconds):
        self.engine = engine
        self.deadline = time.monotonic() + seconds
        self.id = engine.id

    def analyse(self, *args, **kwargs):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Game analysis exceeded its time budget")
        self.engine.timeout = min(30, remaining)
        return self.engine.analyse(*args, **kwargs)


def run_analysis(pgn, color, *, engine_path="stockfish", nodes=100_000, seconds=120):
    validated_game(pgn)  # Reject bad input before creating an external process.
    if color not in ("white", "black") or not 1 <= nodes <= 5_000_000 or not 1 <= seconds <= 600:
        raise ValueError("Choose white/black, 1–5,000,000 nodes and 1–600 seconds")
    engine = chess.engine.SimpleEngine.popen_uci(engine_path, timeout=10)
    try:
        settings = {"Threads": 1, "Hash": 16}
        engine.configure(settings)
        report = analyze_pgn(_BudgetedEngine(engine, seconds), pgn, color, nodes=nodes)
        report["engine"].update(options=settings, max_analysis_seconds=seconds,
                                executable=engine_path)
        return report
    finally:
        # Graceful shutdown is bounded too; close the transport even if quit fails.
        engine.timeout = 5
        try:
            engine.quit()
        finally:
            engine.close()


def _analysis_arguments(parser):
    parser.add_argument("--engine", default="stockfish", help="Stockfish executable path")
    parser.add_argument("--nodes", type=int, default=100_000, help="Node budget per search")
    parser.add_argument("--seconds", type=int, default=120, help="Total analysis budget (1–600 seconds)")
    parser.add_argument("--output", type=Path, required=True, help="New JSON report path")


def _show_candidates(report):
    print("Candidates (ranking loss is not always a centipawn difference):")
    for candidate in report["candidates"]:
        print(f"  ply {candidate['source_ply_count']:3}: "
              f"played {candidate['played_move_san']:7} "
              f"example {candidate['best_move_san']:7} "
              f"ranking loss {candidate['evaluation_loss']}")
    print("Review a candidate explicitly, or reject all; analysis does not establish teaching value.")
    if not report["candidates"]:
        print("No candidate moves for this player. No exercise was generated.")


def _when(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat() if timestamp is not None else "unavailable"


def _show_history(bundle):
    summary, coverage = bundle["summary"], bundle["coverage"]
    print(f"Player: {bundle['username']}")
    latest = summary["latest_reported_rapid"]
    print(f"Latest reported rapid rating: {latest['rating']} at {_when(latest['date'])}" if latest
          else "Latest reported rapid rating/date: unavailable")
    print(f"Requested window: {_when(coverage['requested_start'])} to {_when(coverage['requested_end'])}")
    print(f"Imported sample: {_when(coverage['oldest_imported'])} to {_when(coverage['newest_imported'])}")
    print(f"Games: {summary['game_count']}; results: {summary['results']}; active UTC days: {summary['active_days_utc']}")
    print(f"Complete archive coverage: {coverage['complete']}; capped at 100: {coverage['truncated']}; missing ratings: {summary['missing_ratings']}")
    observations = bundle["endpoint_observations"]
    if observations:
        print(f"Endpoint checks range: {_when(min(o['checked_at'] for o in observations))} to {_when(max(o['checked_at'] for o in observations))}")
    print("API/cache data can lag. Activity and rating history describe only this sample, not a rating plateau.")
    suggestions = set(bundle["suggested_game_ids"])
    for game in bundle["games"]:
        marker = "*" if game["id"] in suggestions else " "
        print(f"{marker} {game['id'][:12]}  {_when(game['end_time'])}  {game['color']}  "
              f"{game['result']}  rating={game['rating']}  vs {game['opponent']}")
    print("* Suggested starting batch: newest five eligible games, not necessarily the most instructive.")
    for warning in bundle["warnings"]:
        print(f"Warning: {warning}")
    if not bundle["games"]:
        print("No eligible games available in this sample. You can still import a PGN manually.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    analyze = commands.add_parser("analyze", help="Analyze one PGN with explicit player color")
    analyze.add_argument("pgn", type=Path)
    analyze.add_argument("--color", choices=("white", "black"), required=True)
    _analysis_arguments(analyze)
    imported = commands.add_parser("import-games", help="Fetch a bounded Chess.com history snapshot")
    imported.add_argument("username")
    imported.add_argument("--refresh", action="store_true", help="Revalidate cached endpoints")
    imported.add_argument("--cache", type=Path, default=Path("generated/import-cache"))
    imported.add_argument("--output", type=Path, required=True)
    selected = commands.add_parser("analyze-import", help="Analyze one selected imported game")
    selected.add_argument("bundle", type=Path)
    selected.add_argument("--game", required=True, help="Unique game ID prefix shown in import output")
    _analysis_arguments(selected)
    review = commands.add_parser("review", help="Record a review; render only accepted candidates")
    review.add_argument("report", type=Path)
    review.add_argument("review", type=Path, help="JSON editorial decision (see examples)")
    review.add_argument("--output", type=Path, required=True, help="New directory for review.json and optional card.html")
    args = parser.parse_args(argv)
    try:
        if args.output.exists():
            raise ValueError(f"Output already exists; choose a new path to preserve it: {args.output}")
        if args.command in ("analyze", "analyze-import"):
            source_import = None
            if args.command == "analyze":
                pgn, color = read_text(args.pgn, MAX_PGN_BYTES), args.color
            else:
                bundle = json.loads(read_text(args.bundle, MAX_JSON_BYTES))
                if bundle.get("schema_version") != 1 or not args.game:
                    raise ValueError("Invalid import bundle or empty game ID")
                matches = [g for g in bundle["games"] if g["id"].startswith(args.game)]
                if len(matches) != 1:
                    raise ValueError("Game ID must identify exactly one imported game")
                selected_game = matches[0]
                pgn, color = selected_game["pgn"], selected_game["color"]
                game = validated_game(pgn)
                if game.headers.get(color.title(), "").casefold() != bundle["username"].casefold():
                    raise ValueError("Imported player/color does not match the PGN")
                source_import = {"game_id": selected_game["id"], "url": selected_game["url"],
                                 "username": bundle["username"], "requested_at": bundle["requested_at"]}
            report = run_analysis(pgn, color, engine_path=args.engine, nodes=args.nodes, seconds=args.seconds)
            if source_import:
                report["source"]["import"] = source_import
            write_json(args.output, report)
            _show_candidates(report)
        elif args.command == "import-games":
            bundle = import_history(ChessComClient(args.cache), args.username, refresh=args.refresh)
            write_json(args.output, bundle)
            _show_history(bundle)
        else:
            report = json.loads(read_text(args.report, MAX_JSON_BYTES))
            decision = json.loads(read_text(args.review, MAX_PGN_BYTES))
            result = review_candidate(report, decision)
            page = None
            if result["card"] is not None:
                card = TrainingCard(**result["card"])
                headers = result["source"]["headers"]
                source_label = (f"{headers.get('White', '?')} vs {headers.get('Black', '?')} · "
                                f"{headers.get('Date', '?')} · ply {card.source_ply_count} · "
                                f"source {result['source']['id'][:12]} · card {result['version_id'][:12]}")
                page = render_training_card(card, source_label=source_label)
            args.output.mkdir(parents=True, exist_ok=False)
            write_json(args.output / "review.json", result)
            if page is not None:
                with (args.output / "card.html").open("x", encoding="utf-8") as handle:
                    handle.write(page)
                print(f"Practice page: {args.output / 'card.html'}")
            else:
                print("Rejection recorded. No exercise generated.")
        print(f"Saved: {args.output}")
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, chess.engine.EngineError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
