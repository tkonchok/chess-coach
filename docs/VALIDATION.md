# Validation log

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
