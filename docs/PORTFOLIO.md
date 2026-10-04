# Portfolio materials — local beta milestone

## Accurate bullets now

- Built a Flask chess-practice workflow that turns completed PGNs into Stockfish-supported positions, interactive move exploration, optional reflections and durable SQLite history.
- Implemented immutable exercise snapshots and transactional, idempotent attempt saving; verified concurrent retries, account-scoped resources and separate database backup/restore.
- Added a bounded SQLite job queue with supervised engine subprocesses, usage quotas and a positions-only AI adapter that preserves engine practice when coaching fails.

Use these only after personally reviewing and understanding the code. Implementation was assisted by an AI coding agent; be candid about that and explain the decisions you can defend. Do not claim public deployment, real Google integration, validated AI teaching quality, improved Elo, users or measured scaling yet.

## Demo

Actual Chromium runs record WebM files in ignored `generated/browser-video/` and narrow-layout screenshots in `generated/browser-white.png` and `generated/browser-black.png`. The recording uses local demo/test accounts and anonymized real-game fixtures. The import response is fixed; Stockfish analysis, board interactions, saving and history are real. AI fallback is demonstrated, not live generated coaching. Review the recording before sharing; it has not been published.

A short narrated recording should show: choose game → analysis status → propose move → reveal/explore → choose optional reflection → save → history → try again. Explain the deliberate no-grade behavior and show a save failure followed by a successful retry. Record live OAuth/AI only after their separate checks.

## Two-minute explanation

“I built a chess-practice app that lets a player revisit decisions from completed games rather than only read an engine's best move. The local beta imports recent rapid games or accepts a PGN. It selects up to three positions, lets the player propose a move, reveals an illustrative continuation, and saves optional reflections for later review.

The backend is Flask and Python with Stockfish. Analysis runs in a supervised subprocess with a fixed deadline and a small SQLite queue. Engine scores use the player's perspective. A position must meet conservative loss and evaluation thresholds and keep the same recommendation in repeated searches; that still does not prove it is a useful lesson.

For history I chose immutable exercise snapshots. Each attempt references exactly the position and explanation presented. A submission ID and database transaction make network retries safe. Account ownership is checked on personal resources. The optional AI adapter sends only bounded position evidence; it excludes identity and reflections and falls back to the engine line.

I worked through the product scope and implementation with AI assistance. I can explain the comparison logic, snapshot design, privacy boundary and failure handling. We checked known score cases, real engine replay, browser interactions with two real games, retry behavior, account isolation and backup restore.

The local workflow is working. The public repository has passing CI, and container verification plus six engine-fact positions across both colors passed. Live hosted Google sign-in and the deployed workflow are still pending. AI commentary stays disabled until its separate review passes. I am not claiming proven chess improvement. After deployment, I plan to use measured demand to guide maintenance and scaling.”

## Walkthrough addition

Accurate completed-work bullet: “Built a Flask chess-practice workflow with bounded Stockfish analysis, paired move-by-move walkthroughs, private SQLite history, and browser tests covering engine failures and save retries.”

Describe AI as structured commentary with reference validation and an engine-fact fallback. The live walkthrough teaching-quality gate has not passed; do not describe the explanations as verified chess coaching, proven visualization training, or deployed production behavior.
