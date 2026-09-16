# Validation log

## 2026-09-15 — Milestone 6A interactive practice slice

Approved scope: local Flask practice, not the complete browser import/review
workflow. Python 3.14.6, chess 1.11.2, Flask 3.1.3; no JavaScript dependency.

- Firefox rendered the first card and legal-destination highlights. Selecting
  an illegal destination left the position unchanged with a legality message.
- Dragging the bishop from c4 to f7 produced Bxf7+, changed the side to move,
  and opened the reasoning step with focus in its field.
- Browser testing caught a request bug (`AbortController.signal` was called as
  a function). It was corrected to use the signal property; requests then worked.
- A subsequent inspection showed the user's reasoning retained alongside the
  revealed line, original Bxf7+ proposal, and separate empty takeaway field.
  The user's text was not overwritten and the page was not reloaded.
- Further navigation/reset checks were blocked by the computer-control guard
  repeatedly reporting application changes. Do not count those checks as passed.
  Keyboard-only board entry, narrow-layout behavior, promotion-dialog interaction,
  skip, undo, finish, and preservation of both notes through navigation still need
  a complete manual pass on this new screen. Earlier offline-page checks below
  do not establish those behaviors for the new implementation. Touch hardware and
  full screen-reader behavior have not been tested.
- Thirteen Flask tests cover the initial/reveal boundary, canonical replay,
  isolated request state, malformed/oversized requests, stale cards, origin/host
  checks, promotions, castling, en passant, checkmate, Black orientation, escaped
  text, and legal replay of the default card. Piece assets omit internal IDs so
  cloning pieces does not create duplicate IDs. These tests do not execute UI JS.
- Full suite: **96 tests passed**, including the opt-in real-Stockfish test.
  `pip check`, JavaScript syntax, and whitespace checks passed. The existing
  python-chess asyncio deprecation warning remains non-failing.

The learner reported that the explanation revealed the overlooked Bxf7+
sacrifice. The transferable takeaway is to examine forcing checks and the
opponent's replies, not simply assume acceptance of a sacrifice. The reviewed
line still uses Kg7, declining the bishop. One useful realization does not prove
retention, rating improvement, or a recurring weakness.

Notes remain page-only and are not sent to the server or AI. No durable storage,
automatic grading, deployment, or new commit is included in this checkpoint.

## 2026-09-15 — Local workflow checkpoint

Environment: Python 3.14.6, chess 1.11.2, local Stockfish 19.
The practice-page implementation was committed locally as `2024569`; nothing was
pushed. Personal instructions and generated/imported artifacts remain excluded.

### Practice page

Manual Firefox check of the generated first card:

- Initial example and playback hidden.
- Tab reaches move, reasoning, and reveal; Return reveals the example.
- Next advances through all four moves; final Next disabled and turn/move label
  reads White to move, move 18 after 17...Qxe8.
- Reset hides the example, restores the starting position, and preserves both
  draft fields. Reload clears drafts as documented; persistence is not implemented.
- At 390×844, the board and form stack and fields wrap inside the viewport.
- Source/game and card-version labels appear in the footer.

These are manual checks, not automated browser regression coverage or a complete
screen-reader audit. Previous/Next behavior also has the earlier local smoke check;
the HTML tests validate frames, visibility defaults, escaping, and IDs, not JS execution.

Editorial lesson: consider forcing checks and count exchanges through the opponent's
recapture. The example does not prove uniqueness, a forced line, or that Ne5 was bad.
A fresh learner attempt and assessment remain outstanding; do not claim measured
learning improvement based on this check.

### Reusable workflow

- Real Stockfish analysis at 25,000 nodes/search produced 20 White comparisons
  for `examples/game.pgn` and 3 Black comparisons for `examples/second-game.pgn`.
- Both reports were used with separate editorial JSON inputs to generate legal,
  traceable cards without editing Python. The second PGN is explicitly synthetic.
- Rejection produced `review.json` and no practice page.
- An opt-in integration test repeats both workflows with temporary artifacts and
  checks provenance and legal replay, never exact engine scores.
- Unit tests cover unchanged domain behavior, report/source validation, import
  filtering and summaries, caching/errors, CLI failures, limits, and cleanup.
- Final check: 82 offline tests passed; the additional real-engine integration
  test passed separately. `pip check` and whitespace checks passed. The pinned
  chess package emits a Python 3.14 deprecation warning for an asyncio helper;
  it does not fail the integration test. No dependency was changed to suppress it.

### Public API smoke check

- Imported the public username already present in the first sample game.
- Profile, statistics, archive listing, and four relevant monthly archives loaded.
- The sample was capped at 100 and the displayed coverage was shorter than the
  requested 90 days; this truncation was explicitly labeled.
- A selected imported Black game passed through the same analyzer with automatic
  color identification (26 comparisons). No automatic lesson was inferred.
- Explicit refresh was exercised successfully with seven conditional cache hits;
  the 100 selected game IDs were unchanged and unique. Imported data and API cache remain
  under ignored `generated/`, not in source control.
- Python's default CA path was missing on this Mac. The smoke command used
  `SSL_CERT_FILE=/etc/ssl/cert.pem` with the existing system trust bundle. Certificate
  verification was not disabled and no new dependency/global setting was added.

### Not validated yet

Varied real-game teaching quality, touch/drag move entry, full screen-reader use,
durable reflections/history, backup restore, browser-only workflow, concurrent
analysis, clean-environment packaging, private access, licensing for distribution,
and deployment. These remain explicit roadmap gates.
