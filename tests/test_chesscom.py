import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from chess_coach.chesscom import ApiError, ChessComClient, import_history


NOW = 1_789_430_400  # Fixed clock: network-free tests must not age out.
BASE = "https://api.chess.com/pub/player/learner"


def archived_game(number, *, color="white", result="win", **changes):
    player = {"username": "Learner", "rating": 1500 + number, "result": result}
    opponent = {"username": "Opponent", "rating": 1490, "result": "resigned"}
    game = {"url": f"https://www.chess.com/game/live/{number}",
            "end_time": NOW - number * 60, "rated": True,
            "rules": "chess", "time_class": "rapid",
            "white": player if color == "white" else opponent,
            "black": player if color == "black" else opponent,
            "pgn": '[White "Learner"]\n[Black "Opponent"]\n[Result "1-0"]\n\n1. e4 e5 1-0'}
    if color == "black":
        game["pgn"] = game["pgn"].replace('[White "Learner"]', '[White "Opponent"]').replace('[Black "Opponent"]', '[Black "Learner"]')
    pgn_result = ("1/2-1/2" if result == "agreed" else
                  "1-0" if (result == "win") == (color == "white") else "0-1")
    game["pgn"] = game["pgn"].replace("1-0", pgn_result)
    return game | changes


class HistoryTests(unittest.TestCase):
    def client(self, games, *, stats=None):
        client = Mock()
        client.observations = []
        responses = {
            BASE: {"username": "Learner", "player_id": 42},
            BASE + "/stats": stats if stats is not None else {
                "chess_rapid": {"last": {"rating": 1550, "date": NOW - 100}}},
            BASE + "/games/archives": {"archives": [BASE + "/games/2026/09"]},
            BASE + "/games/2026/09": {"games": games},
        }
        client.get.side_effect = lambda url, **kwargs: copy.deepcopy(responses[url])
        return client

    def test_selects_both_colors_and_includes_wins_draws_in_recent_suggestions(self):
        client = self.client([archived_game(3, color="black", result="agreed"),
                              archived_game(1), archived_game(2, result="resigned")])
        result = import_history(client, "LEARNER", now=NOW)
        self.assertEqual([g["color"] for g in result["games"]], ["white", "white", "black"])
        self.assertEqual(result["summary"]["results"], {"win": 1, "draw": 1, "loss": 1})
        self.assertEqual(result["suggested_game_ids"], [g["id"] for g in result["games"]])
        self.assertEqual(result["summary"]["latest_reported_rapid"], {"rating": 1550, "date": NOW - 100})
        self.assertEqual(len(result["summary"]["rating_history"]), 3)
        self.assertEqual(result["summary"]["active_days_utc"], 1)
        self.assertEqual(client.get.call_count, 4)

    def test_filters_window_type_completion_and_deduplicates_before_cap(self):
        games = [archived_game(n) for n in range(1, 103)]
        games += [archived_game(1), archived_game(200, rated=False),
                  archived_game(201, rules="chess960"),
                  archived_game(202, time_class="blitz"),
                  archived_game(203, end_time=NOW - 91 * 86400),
                  archived_game(204, end_time=NOW + 10)]
        result = import_history(self.client(games), "learner", now=NOW)
        self.assertEqual(len(result["games"]), 100)
        self.assertTrue(result["coverage"]["truncated"])
        self.assertEqual(result["coverage"]["duplicates_removed"], 1)
        self.assertEqual(result["coverage"]["eligible_found"], 102)
        self.assertEqual(len(result["suggested_game_ids"]), 5)

    def test_missing_rating_is_not_zero_and_empty_history_is_valid(self):
        game = archived_game(1)
        del game["white"]["rating"]
        result = import_history(self.client([game], stats={}), "learner", now=NOW)
        self.assertIsNone(result["summary"]["latest_reported_rapid"])
        self.assertIsNone(result["games"][0]["rating"])
        self.assertEqual(result["summary"]["missing_ratings"], 1)
        empty = import_history(self.client([], stats={}), "learner", now=NOW)
        self.assertEqual(empty["games"], [])
        self.assertIsNone(empty["coverage"]["oldest_imported"])

    def test_month_failure_is_reported_as_partial_coverage(self):
        client = self.client([])
        original = client.get.side_effect
        client.get.side_effect = lambda url, **kw: (
            (_ for _ in ()).throw(ApiError("Rate limited", status=429))
            if url.endswith("2026/09") else original(url, **kw))
        result = import_history(client, "learner", now=NOW)
        self.assertFalse(result["coverage"]["complete"])
        self.assertTrue(any("Rate limited" in warning for warning in result["warnings"]))

    def test_invalid_usernames_and_foreign_archive_urls_are_not_requested(self):
        client = self.client([])
        with self.assertRaises(ValueError):
            import_history(client, "../someone", now=NOW)
        client.get.assert_not_called()
        original = client.get.side_effect
        client.get.side_effect = lambda url, **kw: (
            {"archives": ["https://evil.example/2026/09"]}
            if url.endswith("archives") else original(url, **kw))
        result = import_history(client, "learner", now=NOW)
        self.assertFalse(result["coverage"]["complete"])
        self.assertEqual(client.get.call_count, 3)

    def test_bad_pgn_and_missing_player_are_skipped_with_warning(self):
        game = archived_game(1, pgn="")
        missing = archived_game(2)
        missing["white"]["username"] = "SomeoneElse"
        result = import_history(self.client([game, missing]), "learner", now=NOW)
        self.assertEqual(result["games"], [])
        self.assertEqual(result["coverage"]["invalid_records"], 2)
        self.assertTrue(result["warnings"])

    def test_cutoff_is_inclusive_and_old_archive_months_are_not_fetched(self):
        cutoff = NOW - 90 * 86400
        client = self.client([archived_game(1, end_time=cutoff),
                              archived_game(2, end_time=cutoff - 1)])
        original = client.get.side_effect
        client.get.side_effect = lambda url, **kw: (
            {"archives": [BASE + "/games/2009/01", BASE + "/games/2026/09"]}
            if url.endswith("archives") else original(url, **kw))
        result = import_history(client, "learner", now=NOW)
        self.assertEqual(len(result["games"]), 1)
        self.assertEqual(result["coverage"]["oldest_imported"], cutoff)
        self.assertFalse(any("2009" in call.args[0] for call in client.get.call_args_list))

    def test_conflicting_result_and_unfinished_pgn_are_not_imported(self):
        wrong = archived_game(1)
        wrong["white"]["result"] = "resigned"
        unfinished = archived_game(2, pgn='[White "Learner"]\n\n1. e4 *')
        result = import_history(self.client([wrong, unfinished]), "learner", now=NOW)
        self.assertEqual(result["games"], [])
        self.assertEqual(result["coverage"]["invalid_records"], 2)

    def test_rate_limit_stops_before_requesting_older_months(self):
        client = self.client([])
        original = client.get.side_effect

        def respond(url, **kwargs):
            if url.endswith("archives"):
                return {"archives": [BASE + "/games/2026/08", BASE + "/games/2026/09"]}
            if url.endswith("2026/09"):
                raise ApiError("Rate limited", status=429)
            return original(url, **kwargs)

        client.get.side_effect = respond
        result = import_history(client, "learner", now=NOW)
        self.assertFalse(result["coverage"]["complete"])
        self.assertFalse(any(call.args[0].endswith("2026/08") for call in client.get.call_args_list))

    def test_unavailable_username_aborts_without_a_fake_empty_history(self):
        client = self.client([])
        client.get.side_effect = ApiError("unavailable", status=404)
        with self.assertRaisesRegex(ApiError, "unavailable"):
            import_history(client, "learner", now=NOW)
        self.assertEqual(client.get.call_count, 1)


class ClientTests(unittest.TestCase):
    def test_cache_avoids_request_and_explicit_refresh_revalidates(self):
        transport = Mock(side_effect=[(200, {"etag": "v1", "cache-control": "max-age=3600"},
                                       b'{"username":"learner"}'), (304, {}, b"")])
        with tempfile.TemporaryDirectory() as directory:
            client = ChessComClient(Path(directory), transport=transport, clock=lambda: NOW)
            first = client.get(BASE)
            self.assertEqual(client.get(BASE), first)
            self.assertEqual(transport.call_count, 1)
            self.assertEqual(client.get(BASE, refresh=True), first)
            self.assertEqual(transport.call_args.args[1]["If-None-Match"], "v1")
            self.assertEqual(transport.call_count, 2)
            self.assertEqual(client.observations[-1]["checked_at"], NOW)

    def test_errors_are_clear_and_not_retried(self):
        for status, message in ((404, "unavailable"), (429, "Rate limited"), (503, "503")):
            with tempfile.TemporaryDirectory() as directory:
                transport = Mock(return_value=(status, {"retry-after": "60"}, b""))
                client = ChessComClient(Path(directory), transport=transport)
                with self.subTest(status=status), self.assertRaisesRegex(ApiError, message):
                    client.get(BASE)
                self.assertEqual(transport.call_count, 1)

    def test_rejects_invalid_json_foreign_hosts_and_excess_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            transport = Mock(return_value=(200, {}, b"not json"))
            client = ChessComClient(Path(directory), transport=transport, max_requests=1)
            with self.assertRaisesRegex(ApiError, "JSON"):
                client.get(BASE)
            with self.assertRaisesRegex(ApiError, "budget"):
                client.get(BASE)
            with self.assertRaises(ValueError):
                client.get("https://evil.example/")

    def test_corrupt_cache_is_discarded(self):
        with tempfile.TemporaryDirectory() as directory:
            transport = Mock(return_value=(200, {}, json.dumps({"ok": True}).encode()))
            client = ChessComClient(Path(directory), transport=transport)
            client.get(BASE)
            # Editing a disposable cache is test setup, not application behavior.
            next(Path(directory).glob("*.json")).write_text("broken")
            self.assertEqual(client.get(BASE), {"ok": True})
            self.assertEqual(transport.call_count, 2)

    def test_response_size_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            transport = Mock(return_value=(200, {}, b"x" * 10_000_001))
            client = ChessComClient(Path(directory), transport=transport)
            with self.assertRaisesRegex(ApiError, "10 MB"):
                client.get(BASE)
            self.assertEqual(list(Path(directory).glob("*.json")), [])

    def test_no_store_refresh_removes_previous_disposable_cache(self):
        transport = Mock(side_effect=[(200, {}, b'{"x":1}'),
                                     (200, {"Cache-Control": "no-store"}, b'{"x":2}')])
        with tempfile.TemporaryDirectory() as directory:
            client = ChessComClient(Path(directory), transport=transport)
            client.get(BASE)
            self.assertEqual(client.get(BASE, refresh=True), {"x": 2})
            self.assertEqual(list(Path(directory).glob("*.json")), [])
