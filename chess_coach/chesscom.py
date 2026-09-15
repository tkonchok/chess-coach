"""Bounded, read-only Chess.com imports using the public completed-game API."""

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from chess_coach.workflow import validated_game


API = "https://api.chess.com/pub/player/"
MAX_RESPONSE_BYTES = 10_000_000
DRAW_RESULTS = {"agreed", "repetition", "stalemate", "insufficient", "50move", "timevsinsufficient"}
LOSS_RESULTS = {"checkmated", "timeout", "resigned", "lose", "abandoned"}


class ApiError(RuntimeError):
    def __init__(self, message, *, status=None):
        super().__init__(message)
        self.status = status


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never follow an API-provided redirect to an arbitrary host.


def _request(url, headers):
    opener = build_opener(_NoRedirect())
    try:
        with opener.open(Request(url, headers=headers), timeout=15) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
            return response.status, dict(response.headers.items()), body
    except HTTPError as error:
        try:
            return error.code, dict(error.headers.items()), b""
        finally:
            error.close()
    except (URLError, OSError) as error:
        raise ApiError(f"Chess.com request failed: {error}") from error


class ChessComClient:
    """Serial requests with disposable on-disk cache and explicit revalidation.

    Default budget: profile + stats + archive index + at most four months.
    No automatic retries or stale-on-error fallback. Instantiate per import.
    """

    def __init__(self, cache_dir: Path, *, transport=_request, clock=time.time,
                 max_requests=7):
        self.cache_dir = Path(cache_dir)
        self.transport = transport
        self.clock = clock
        self.max_requests = max_requests
        self.requests = 0
        self.observations = []

    def get(self, url: str, *, refresh=False) -> dict:
        if not re.fullmatch(r"https://api\.chess\.com/pub/player/[a-z0-9_-]+(?:/stats|/games/archives|/games/\d{4}/(?:0[1-9]|1[0-2]))?", url):
            raise ValueError("Only expected Chess.com public player endpoints are allowed")
        path = self.cache_dir / (sha256(url.encode()).hexdigest() + ".json")
        cached = None
        try:
            if path.stat().st_size <= MAX_RESPONSE_BYTES * 2:
                entry = json.loads(path.read_text(encoding="utf-8"))
                if (entry["url"] == url and isinstance(entry["data"], dict)
                        and isinstance(entry["expires_at"], (int, float))
                        and isinstance(entry["fetched_at"], (int, float))
                        and isinstance(entry["checked_at"], (int, float))
                        and isinstance(entry["etag"], str)):
                    cached = entry
        except (OSError, ValueError, KeyError, TypeError):
            pass  # Cache is an optimization; corrupt entries are not source data.
        now = int(self.clock())
        if cached and not refresh and cached["expires_at"] > now:
            self._observe(cached, from_cache=True)
            return cached["data"]
        if self.requests >= self.max_requests:
            raise ApiError("Chess.com request budget exhausted; refresh later")
        headers = {"User-Agent": "ChessCoachPrivatePrototype/0.1",
                   "Accept": "application/json"}
        if cached and cached["etag"]:
            headers["If-None-Match"] = cached["etag"]
        self.requests += 1
        status, response_headers, body = self.transport(url, headers)
        response_headers = {k.lower(): v for k, v in response_headers.items()}
        if status == 429:
            retry = response_headers.get("retry-after", "the server's suggested interval")
            raise ApiError(f"Rate limited by Chess.com; retry after {retry}. No automatic retry.", status=status)
        if status in (404, 410):
            raise ApiError("Chess.com username or resource unavailable", status=status)
        if status not in (200, 304) or (status == 304 and cached is None):
            raise ApiError(f"Chess.com returned HTTP {status}", status=status)
        if len(body) > MAX_RESPONSE_BYTES:
            raise ApiError("Chess.com response exceeds the 10 MB limit")
        if status == 304:
            entry = cached.copy()
        else:
            try:
                data = json.loads(body)
                if not isinstance(data, dict):
                    raise ValueError("Expected an object")
            except (ValueError, UnicodeError) as error:
                raise ApiError("Chess.com returned invalid JSON data") from error
            entry = {"url": url, "data": data, "fetched_at": now,
                     "etag": response_headers.get("etag", "")}
        cache_control = response_headers.get("cache-control", "")
        max_age = re.search(r"max-age=(\d+)", cache_control)
        ttl = min(int(max_age[1]), 86400) if max_age else 3600
        if "no-cache" in cache_control or "no-store" in cache_control:
            ttl = 0
        entry.update(checked_at=now, expires_at=now + ttl)
        if "no-store" not in cache_control:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            # Replace only this disposable cache key, never a user artifact.
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(entry), encoding="utf-8")
            temporary.replace(path)
        else:
            path.unlink(missing_ok=True)
        self._observe(entry, from_cache=status == 304)
        return entry["data"]

    def _observe(self, entry, *, from_cache):
        self.observations.append({key: entry[key] for key in ("url", "fetched_at", "checked_at")} |
                                 {"from_cache": from_cache})


def _date(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat()


def _eligible_game(raw, username, start, end):
    """None means intentionally out of scope; ValueError means incomplete/bad data."""
    if not isinstance(raw, dict):
        raise ValueError("Invalid game record")
    if raw.get("rated") is not True or raw.get("rules") != "chess" or raw.get("time_class") != "rapid":
        return None
    finished = raw.get("end_time")
    if type(finished) is not int:
        raise ValueError("Missing game completion timestamp")
    if not start <= finished <= end:
        return None
    colors = [color for color in ("white", "black")
              if raw.get(color, {}).get("username", "").casefold() == username]
    if len(colors) != 1:
        raise ValueError("Cannot identify the player's color")
    color = colors[0]
    player = raw[color]
    result_code = player.get("result")
    if result_code == "win":
        outcome = "win"
    elif result_code in DRAW_RESULTS:
        outcome = "draw"
    elif result_code in LOSS_RESULTS:
        outcome = "loss"
    else:
        raise ValueError("Missing or unknown completed-game result")
    url, pgn = raw.get("url"), raw.get("pgn")
    if not isinstance(url, str) or not re.fullmatch(r"https://www\.chess\.com/game/(?:live|daily)/\d+", url):
        raise ValueError("Missing or invalid source-game URL")
    if not isinstance(pgn, str) or not pgn.strip():
        raise ValueError("Missing PGN")
    game = validated_game(pgn)
    if (game.headers.get(color.title(), "").casefold() != username
            or game.headers.get("Result") not in ("1-0", "0-1", "1/2-1/2")):
        raise ValueError("PGN does not identify the same player or a completed game")
    pgn_result = game.headers["Result"]
    pgn_outcome = ("draw" if pgn_result == "1/2-1/2" else
                   "win" if (pgn_result == "1-0") == (color == "white") else "loss")
    if outcome != pgn_outcome:
        raise ValueError("Archive result conflicts with its PGN")
    rating = player.get("rating")
    return {"id": sha256(url.encode()).hexdigest(), "url": url, "pgn": pgn,
            "color": color, "end_time": finished, "result": outcome,
            "result_code": result_code,
            "rating": rating if type(rating) is int else None,
            "opponent": raw.get("black" if color == "white" else "white", {}).get("username")}


def import_history(client: ChessComClient, username: str, *, now=None, refresh=False) -> dict:
    """Import a 90-day sample, capped at the newest 100 eligible unique games."""
    username = username.strip().casefold()
    if not re.fullmatch(r"[a-z0-9_-]{1,50}", username):
        raise ValueError("Enter a Chess.com username, not a URL")
    now = int(time.time() if now is None else now)
    start = now - 90 * 86400
    base = API + username
    profile = client.get(base, refresh=refresh)
    if not isinstance(profile.get("username"), str):
        raise ApiError("Chess.com returned a profile without a username")
    if profile["username"].casefold() != username:
        raise ApiError(f"Profile has a different username; retry using {profile['username']}")
    warnings = []
    try:
        stats = client.get(base + "/stats", refresh=refresh)
    except ApiError as error:
        if error.status == 429:
            raise  # Do not make more requests immediately after a rate limit.
        warnings.append(f"Statistics unavailable: {error}")
        stats = {}
    index = client.get(base + "/games/archives", refresh=refresh).get("archives")
    if not isinstance(index, list):
        raise ApiError("Chess.com archive index is missing or invalid")
    months = []
    complete = True
    for url in index:
        match = re.fullmatch(re.escape(base) + r"/games/(\d{4}/(?:0[1-9]|1[0-2]))", url) if isinstance(url, str) else None
        if not match:
            warnings.append("Ignored an unexpected archive URL")
            complete = False
        elif _date(start)[:7].replace("-", "/") <= match[1] <= _date(now)[:7].replace("-", "/"):
            months.append(url)
    months = sorted(set(months), reverse=True)
    if len(months) > 4:
        raise ApiError("Archive list exceeded the 90-day request bound")
    games_by_id = {}
    invalid = duplicates = 0
    fetched_months = []
    for url in months:
        try:
            records = client.get(url, refresh=refresh).get("games")
            if not isinstance(records, list) or len(records) > 20_000:
                raise ApiError("Monthly archive is missing or exceeds 20,000 records")
        except ApiError as error:
            complete = False
            warnings.append(f"Archive {url.rsplit('/', 2)[-2:]} unavailable: {error}")
            if error.status == 429:
                break
            continue
        fetched_months.append(url)
        for raw in records:
            try:
                game = _eligible_game(raw, username, start, now)
            except (ValueError, TypeError, AttributeError):
                invalid += 1
                continue
            if game is not None:
                if game["id"] in games_by_id:
                    duplicates += 1
                else:
                    games_by_id[game["id"]] = game
    ordered = sorted(games_by_id.values(), key=lambda g: (-g["end_time"], g["id"]))
    games = ordered[:100]
    if invalid:
        warnings.append(f"Skipped {invalid} incomplete or invalid eligible records")
        complete = False
    rapid = stats.get("chess_rapid", {})
    last = rapid.get("last", {}) if isinstance(rapid, dict) else {}
    latest = ({"rating": last["rating"], "date": last["date"]}
              if isinstance(last, dict) and type(last.get("rating")) is int
              and type(last.get("date")) is int else None)
    if latest is None:
        warnings.append("Latest reported rapid rating/date unavailable")
    activity = Counter(_date(g["end_time"]) for g in games)
    results = Counter(g["result"] for g in games)
    return {
        "schema_version": 1, "username": username,
        "profile": {key: profile.get(key) for key in ("username", "player_id", "url")},
        "requested_at": now, "explicit_refresh": refresh,
        "endpoint_observations": list(client.observations),
        "coverage": {"requested_start": start, "requested_end": now,
                     "oldest_imported": games[-1]["end_time"] if games else None,
                     "newest_imported": games[0]["end_time"] if games else None,
                     "complete": complete, "truncated": len(ordered) > 100,
                     "eligible_found": len(ordered), "duplicates_removed": duplicates,
                     "invalid_records": invalid, "archives_fetched": fetched_months},
        "summary": {"game_count": len(games), "latest_reported_rapid": latest,
                    "results": {key: results[key] for key in ("win", "draw", "loss")},
                    "active_days_utc": len(activity), "games_by_date_utc": dict(sorted(activity.items())),
                    "missing_ratings": sum(g["rating"] is None for g in games),
                    "rating_history": [{"date": g["end_time"], "rating": g["rating"], "game_id": g["id"]}
                                       for g in reversed(games) if g["rating"] is not None]},
        "games": games, "suggested_game_ids": [g["id"] for g in games[:5]],
        "warnings": warnings,
    }
