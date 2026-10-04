# Browser beta architecture

## Input to output

`beta.py` receives a signed-in user's username or completed PGN. The existing importer bounds public rapid history and preserves coverage warnings. The user explicitly chooses one game. `storage.py` atomically checks quota/queue limits and records a job. `jobs.py` claims the oldest job and launches `worker.py` in a separate process group. The worker uses the same bounded engine runner as the CLI.

`analysis.py` compares the played move with a candidate from the mover's perspective. `exercises.py` filters the first eight ranked candidates, repeats comparisons at twice the node budget, obtains up to three alternative lines, and legally replays each continuation. It retains at most three stable positions. An empty result is a successful analysis with no suitable practice positions, not a fabricated lesson.

The practice adapter reconstructs every submitted move path from the saved card. It never accepts an arbitrary browser FEN. The first proposed move is stored separately from later exploration. Reveal returns an illustrative engine line without grading the proposal. Optional coaching is an explicit positions-only request. Save links the attempt to an immutable snapshot and returns its history URL.

## Five concepts to understand

- [x] Input/output: selected PGN → queued bounded job → positions → practice → saved history.
- [ ] Comparison versus lesson selection: a large engine loss alone does not establish a useful lesson. Search stability and a human teaching-quality review are separate checks.
- [ ] Failure handling: malformed input is rejected; timeouts save no partial analysis; unavailable AI leaves the legal engine line available.
- [x] Immutable history and retries: the exercise version preserves exactly what was presented. A UUID submission and unchanged payload make a retry the same save, not a second attempt. Deletion leaves a tombstone so delayed retries cannot resurrect notes.
- [ ] Verification: deterministic comparison fixtures, real engine replay, browser interactions, cross-account checks and backup restore cover different failure modes.

Checkmarks indicate discussion milestones, not an assessment of mastery. The user explained that exact versions allow revisiting the session and learning; the additional invariant is that future reanalysis cannot silently change that history. The reserved user implementation task is the history empty-state message in `templates/beta_history.html`.

## Persistence and trust

SQLite schema version 1 is created through explicit statements in a transaction. Unknown schema versions and nonempty unversioned databases fail closed. Every personal read/write requires a user ID. Queries use bound parameters. Durable records include users, hashed opaque server-session tokens, games, imports, jobs/results, exercise snapshots, attempts, UTC-day usage counters and successful position-only explanation caches.

Authlib handles Google OpenID Connect. Only a local identity and opaque session are retained, not access tokens. A signed cookie holds a server-session token and CSRF nonce; personal content is stored server-side. Mutation routes check CSRF and reject foreign origins. `LOCAL_DEMO` is localhost-only and cannot be enabled on a public origin.

AI evidence is constructed using an explicit allowlist in `coaching.py`, excluding the source PGN and all personal fields. JSON schema, bounded text and move-reference checks reject malformed explanations. They do not detect every false chess statement. Coaching cache keys include exercise version, model and prompt version.

## Deliberate tradeoffs

The narrated walkthrough replaces the earlier prediction UI. Preparation accepts the owned card ID and a legal proposed move, reconstructs the root server-side, and obtains up to six plies for each proposed/recommended branch at matching 50,000-node/0.5-second and 100,000-node/1-second budgets. Both searches are retained; ranking changes or mate comparisons are marked uncertain. One engine slot and a 12-second process-group deadline bound preparation. Board facts include captures (including en passant), promotions, checks, direct attacks and fixed-value material changes. Facts describe the illustrative line without establishing forced wins or trapped pieces.

A second scoped route accepts the prepared walkthrough ID and explicit positions-only consent, loads trusted cached evidence, and requests the complete branch/ply commentary bundle once. The payload is an allowlist excluding identity, PGNs and reflections. Commentary validators check exact branch/ply coverage, current fact IDs, past/current SAN and cited squares, plus basic certainty wording; this does not prove all natural-language claims. Evidence caches are scoped to user/exercise/proposal/engine protocol; successful commentary caches include exercise, proposal, evidence digest, model and prompt version. Existing cache tables are reused without migration. These caches are not saved attempts.

Browser navigation chooses a branch and ply; commentary for future plies stays hidden. Sequence and walkthrough IDs reject stale responses after leaving/replacing a walkthrough. AI loading does not lock move navigation or saving. Live short-search evaluation remains optional and separate from the recorded root comparison; best-move arrows pause during the fixed-line walkthrough in favor of evidence-reference square highlights. Public AI walkthroughs default off until the teaching review passes; localhost testing permits preview. Ordinary free exploration and the offline tools remain.

Live exploration replays the owned exercise and legal move path server-side. It shares a nonblocking engine lock with full-game jobs: a busy engine returns an actionable message while practice and saving remain available. Each position search uses at most 25,000 nodes/0.35 seconds with a five-second subprocess deadline. Client-side debouncing, a bounded FEN cache and stale-response checks avoid unnecessary searches and prevent old results appearing on a new position. Scores always use White's perspective, independently of board orientation. Live searches have separate UTC-day allowances: 100/account and 300 globally (allowance bypassed in localhost testing). Terminal positions need no engine search. No reflection fields enter engine requests.

One Gunicorn process with request threads and one supervised analysis subprocess avoids Redis and a separate worker service. A SQLite-backed queue survives restart; previously running work is marked failed, queued work can resume. A file lock prevents two supervisors sharing the same database. This implementation requires a POSIX host and is intended for one instance.

Jobs have a 240-second supervisor deadline, one Stockfish thread and 16 MiB hash. Linux adds process address-space/CPU limits. Process-group termination cleans up Stockfish children. Shutdown and a platform restart may fail active work rather than resume partial engine state.

Limits: one active job/account; three waiting jobs globally; one analysis/account/day and 30 globally; five AI requests/account/day and 100 globally. Successful explanations are cached. Import requests are also bounded (five/account/day, 100 globally); at most 500 stored games/account. Failed accepted work consumes its reserved daily allowance. Saved practice remains usable at quota exhaustion. Explicit `LOCAL_TESTING=1` raises the per-account analysis and import allowances to 20 each on localhost; public origins reject it, and global/queue limits remain.

Optional local reflection summaries are not implemented. Whole-history analysis, generated similar puzzles, unrestricted engine opponents, conversational reflections, adaptive scheduling and rating diagnosis are deferred.

### Library presentation

The Puzzles view joins owned exercise snapshots to non-deleted attempts, then groups by PGN source digest and player color. Counts are per immutable exercise version, not per attempt; a repeat save does not increase the practiced-position total. Filters hide cards while keeping each group's full progress count. Original headers and move numbers come from retained snapshots, so removing an imported game does not remove its practice context. Results use the same position-card partial and ownership-scoped image routes. The signed-out SVG preview is generated from a fixed illustrative position and contains no personal data. No schema migration or new AI call is involved.

## Archive browsing

`GET /archive` fetches the public archive index and one selected month serially through the existing constrained, TLS-verified Chess.com client (maximum two uncached requests). The monthly raw response is capped at 10 MB/20,000 records; cheap metadata filtering and deduplication precede legal PGN replay for at most 50 records per page. The browser can select any published month and standard time control; recent rapid import keeps its 90-day/100-game behavior.

The owned imports row holds only the current browsed page. Thumbnail/source lookup can use that page, without populating durable games for every page visited. Selecting analysis copies the game into the existing durable owned games table before queueing; navigating away cannot remove a queued job’s source. No migration, AI request, or automatic whole-history analysis. Public browsing allows 60 page views per account daily/600 installation-wide (localhost testing 200 per account); analysis quotas and the 500 durable-source-game account cap remain. Other accounts cannot use transient source IDs.
