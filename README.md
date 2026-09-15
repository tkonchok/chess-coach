# Chess Training & Analysis

A personal chess training tool that turns completed games into focused practice.

The long-term goal is to help players understand recurring weaknesses in their play, train important positions from their own games, and develop better decision-making habits rather than only viewing engine-best moves.

## Project Status

Local prototype. PGN analysis, explicit editorial review, offline practice pages,
and bounded Chess.com username import now work through command-line tools.
The browser-only workflow, board move entry, durable reflections, and deployment
are not implemented yet. See the [roadmap](docs/ROADMAP.md) and
[validation log](docs/VALIDATION.md) for completed work and remaining gates.

## V1 Product Hypothesis

A self-taught intermediate chess player will find training more useful when important positions from their own games are turned into personalized exercises with clear explanations and optional coaching around their original reasoning.

## V1 Scope

The initial version will focus on:

- username import of completed, rated, standard Chess.com rapid games, with PGN fallback
- factual recent-game activity and rating summaries with coverage warnings
- exact positions from the player's own games
- identifying meaningful mistakes, misses, and important decisions
- practicing by playing on the board before revealing a reviewed example
- concise explanations, including alternative strong moves and uncertainty
- saved practice history and reflections

Conversational coaching, learner memory, and history-guided recommendations follow
the first private deployment. The current practice page still uses text move entry.
Its examples are not automatic right/wrong grading.

## Not in V1

The initial version will not include:

- live-game assistance
- blitz or bullet analysis
- browser-extension behavior tracking
- generated or similar puzzle positions
- spaced repetition
- comprehensive opening or endgame courses
- social features
- rating prediction
- advanced analytics dashboards

## Core Product Principle

Engine analysis helps detect candidate mistakes.

The product must still decide whether a position is actually worth training.

The coaching layer should distinguish between:

- what happened on the board
- what the player was trying to accomplish
- what lesson could transfer to future games

The system must not pretend to know why a player made a move without evidence from the player.

## Current Engineering Direction

V1 is planned as a web application with server-side chess analysis.

Current decisions:

- Python for the server-side chess-analysis pipeline
- Chess.com Public Data API for completed-game data
- heavy chess analysis performed outside the browser
- core chess/training logic should remain independent enough to support other interfaces in the future

Frameworks, database technology, production chess-engine packaging, frontend stack,
AI models, and deployment providers have not yet been finalized. Stockfish runs
locally; command adapters and disposable JSON artifacts do not introduce a server
or database. The only Python dependency remains `chess==1.11.2`.

## Local Development

Create and activate the Python environment, then install the Python dependency:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Milestone 3 uses a local Stockfish executable for its engine-analysis spike:

```bash
brew install stockfish
```

Run the automated tests from the project root:

```bash
python -m unittest discover -s tests -v
```

The `chess` Python package and Stockfish use GPL licenses. Licensing must be reviewed before distributing the application.

### Try the local practice page

From the project root, generate the first card:

```bash
.venv/bin/python -m examples.first_card
```

Open `generated/first-card.html` in your browser. On macOS you can use:

```bash
open generated/first-card.html
```

Study the board, type your proposed move and reasoning, then select **Reveal
example**. Use **Previous** and **Next** to step through the continuation.
**Return to starting position** hides the example and resets the board while
keeping your typed notes. The board is a viewer; moves are entered as text,
not by dragging pieces. Answers are not graded, saved, or sent anywhere.

The file works offline with inline SVG boards, CSS, and JavaScript. Stockfish
is not needed to generate this already-reviewed example. There is no web
framework or server. Re-running the command replaces the generated page;
`generated/` is ignored by Git. The shared sample PGN lives in `examples/game.pgn`.

The implementation has three small parts: `training.py` holds the card data,
`presentation.py` renders each legal board position, and `templates/card.html`
controls presentation and navigation. The example generator connects them.

### Analyze and review another game

No application-code changes are required. From the project root:

```bash
.venv/bin/python -m chess_coach analyze examples/game.pgn --color white --output generated/analysis.json
.venv/bin/python -m chess_coach review generated/analysis.json examples/first-review.json --output generated/reviewed-card
open generated/reviewed-card/card.html
```

`analyze` prints ranked candidates and saves the source PGN, its SHA-256 document
ID, headers, selected color, exact ply/FEN/move, evaluations, engine identity,
library version, settings, and timestamp. A ply is one move by one side; ply 30
means the board before White's 16th move in a normal game. Losses involving mate
use synthetic ranking values, not literal centipawns.

To use your own game, change the PGN path and color, inspect the candidates, and
supply an editorial JSON file modeled on `examples/first-review.json`. Read the
[review checklist](docs/TRAINING_REVIEW.md). Acceptance requires a reason, legal
SAN continuation, explanation, and notes about alternatives. Rejection requires a
reason but produces no HTML. Leaving all candidates unaccepted is also valid.

The report is input to `review`; don't edit its source or candidate position.
`review` checks source integrity and replay, then saves a versioned snapshot in
`review.json` beside the HTML. Digest IDs detect accidental changes, not malicious
tampering. A document ID is not a universal game identity: reformatting a PGN
changes that ID. Imported games additionally retain a stable source-URL ID.

Try the same workflow for Black using a deliberately synthetic second game:

```bash
.venv/bin/python -m chess_coach analyze examples/second-game.pgn --color black --output generated/second-analysis.json
.venv/bin/python -m chess_coach review generated/second-analysis.json examples/second-review.json --output generated/second-card
```

Output paths must be new: these commands refuse to overwrite previous reports or
cards. Use another name when rerunning. Generated outputs are ignored by Git.

### Import from Chess.com

```bash
.venv/bin/python -m chess_coach import-games YOUR_USERNAME --output generated/history.json
```

The command fetches public data, not account credentials. It selects the newest
100 eligible games within 90 days, identifies color, and prints results, activity,
reported rapid rating/date, sample coverage, truncation, and missing-data warnings.
The JSON also contains daily activity and observed per-game rating history. The
starred five-game suggestion uses recency regardless of wins/draws/losses; it does
not diagnose weaknesses or claim these are optimal training games.

Choose any game's displayed ID prefix, not just a starred game:

```bash
.venv/bin/python -m chess_coach analyze-import generated/history.json --game GAME_ID_PREFIX --output generated/imported-analysis.json
```

Then use the same `review` command with your reviewed decision. Analyze selected
games one at a time in this command workflow; there is not yet a background queue.

To refresh explicitly, choose a new output snapshot:

```bash
.venv/bin/python -m chess_coach import-games YOUR_USERNAME --refresh --output generated/history-refreshed.json
```

Requests are serial, capped at seven per import, with a 15-second socket timeout
and 10 MB response limit. Only relevant archive months are fetched. Disposable
cache entries live in `generated/import-cache`, obey freshness directives, and
use ETag revalidation. A cache with zero freshness still needs the network.
Refresh cannot force Chess.com's own data to be current. Rate limits are reported
without automatic retry; monthly failures explicitly mark partial coverage.
Game URLs provide deduplication within each snapshot and stable IDs across refreshes.
Durable cross-session merging/history is milestone 7, not this cache.

The endpoint contracts and rating meanings come from the
[official Chess.com Public Data API documentation](https://www.chess.com/news/view/published-data-api).
Data from the statistics endpoint is separate from the imported sample: do not
interpret 100 games as a complete 90-day history or calculate an undefined
“time at this rating” measure from it.

On this Mac, Python's default certificate file was missing. A verified local
workaround uses the existing system CA bundle for this command only:

```bash
SSL_CERT_FILE=/etc/ssl/cert.pem .venv/bin/python -m chess_coach import-games YOUR_USERNAME --output generated/history.json
```

Use a valid trust store appropriate to your environment; never disable TLS
verification. No certificate dependency or global setting was changed.

### Limits and verification

The command workflow accepts at most 1 MB PGNs and 1,000 main-line plies, and
currently requires standard chess from the normal starting position. Analysis
uses one Stockfish process, one thread, and 16 MiB hash. Defaults are 100,000 nodes
per search and a 120-second shared analysis deadline; use `--nodes` and `--seconds`
to change them within the documented command limits. Searches have a maximum
30-second response timeout. Startup/shutdown have separate bounds. Failures do
not produce partial candidate reports, and cleanup is attempted in `finally`.
These are local command safeguards, not a production resource-isolation system.

```bash
.venv/bin/python -m unittest discover -s tests -v
RUN_STOCKFISH_TESTS=1 .venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m pip check
```

The default suite is network-free and skips the real-engine integration test.
The opt-in suite needs `stockfish` on PATH and runs both example games through
analysis, review, and legal card replay without asserting exact scores. Browser
interactions still have manual smoke coverage, not an automated browser suite.

New code boundaries: `workflow.py` connects chess analysis to editorial review;
`chesscom.py` imports and summarizes public data; `__main__.py` handles arguments,
files, and engine lifetime. Core comparison and card-building functions remain
independent of the eventual web framework.

## Current Milestone

### Milestone 3 — One End-to-End Training Card

Goal:

Starting from one completed rapid game, produce one usable personalized training position through the real software pipeline.

Completed slices:

- **3A — PGN position retrieval:** parse one PGN, reconstruct its main line, and retrieve the exact position after a requested number of plies.
- **3B — One-move engine comparison:** compare a played move with a Stockfish candidate using a fixed-node, paired MultiPV search and retain explicit centipawn or mate evaluations.
- **3C — Rank player moves:** replay one game, compare the selected color's moves, and return comparisons in descending evaluation-loss order. Ties retain game order.
- **3D — First card data:** build a practice-and-reveal card from an explicitly selected position, preserving its FEN, actual played move, reviewed example continuation, and explanation. Each continuation move is checked for legality.
- **3E — Local practice page:** view the first card in a browser, enter a move and reasoning, reveal an example, and step through its positions without a server.

The first manually reviewed card runs through a local browser interface.
Technical 3F checks are recorded in the validation log; the learner's fresh
usefulness assessment remains open. Milestone 4's reusable/import workflows now
exist as command adapters. Milestone 5 has an explicit review checklist, but still
needs a varied real-game quality assessment. The highest engine loss is not
automatically the best teaching position.

No web framework, database, server, training-label thresholds, or AI coaching
layer has been added. The next web step is to review the screens listed in the
roadmap before choosing a framework or board library.

Stockfish 19 characterization for the position before `16.Ne5` on 2026-09-09:

| Nodes | Paired best move | Best evaluation | `Ne5` evaluation | Loss |
| ---: | --- | ---: | ---: | ---: |
| 25,000 | `Bxf7+` | +751 cp | +669 cp | 82 cp |
| 100,000 | `Bxf7+` | +780 cp | +653 cp | 127 cp |
| 500,000 | `Bxf7+` | +802 cp | +773 cp | 29 cp |

These are environment-specific observations, not stable expected values or training labels.

### Running the game-wide analysis experiment

`analyze_player_moves(engine, game, player_color, *, nodes=100_000)` returns a
`list[MoveComparison]`. Select the player with `chess.WHITE` or `chess.BLACK`.
The node budget applies to each search, not the entire game: a comparison uses
one seed search and, when necessary, one paired search. The same engine process
is reused across the game. Empty games or games with no moves for the selected
color return an empty list. Non-positive budgets raise `ValueError`, even for
empty games. Analysis errors propagate without returning a partial ranking.

Run this manual experiment from the project root using the existing test PGN:

```bash
.venv/bin/python - <<'PY'
import runpy
import chess
import chess.engine
from chess_coach.analysis import analyze_player_moves
from chess_coach.pgn import parse_pgn

pgn = runpy.run_path("tests/test_pgn.py")["CHESS_COM_PGN"]
game = parse_pgn(pgn)
engine = chess.engine.SimpleEngine.popen_uci("stockfish")
try:
    ranked = analyze_player_moves(engine, game, chess.WHITE, nodes=100_000)
finally:
    engine.quit()

for comparison in ranked[:5]:
    board = chess.Board(comparison.position_fen)
    print(f"{board.fullmove_number}.{comparison.played_move_san}",
          f"best={comparison.best_move_san}",
          f"loss={comparison.evaluation_loss}")
    print("best evaluation:", comparison.best_evaluation)
    print("played evaluation:", comparison.played_evaluation)
PY
```

`runpy` loads the existing fixture for this manual experiment; production domain
code does not import tests. The caller starts and closes Stockfish. Keeping
`quit()` in `finally` ensures cleanup is attempted even if analysis fails.
The game is left unchanged, and every comparison retains its pre-move FEN.

A Stockfish 19 run on 2026-09-14 analyzed all 20 White moves at 100,000 nodes per
search in approximately 5.7 seconds. The five highest observed losses were:

| Played move | Paired best move | Best evaluation | Played evaluation | Loss |
| --- | --- | ---: | ---: | ---: |
| `14.b3` | `Ne5` | +761 cp | +609 cp | 152 |
| `16.Ne5` | `Bxf7+` | +751 cp | +642 cp | 109 |
| `3.f4` | `Nf3` | +33 cp | -51 cp | 84 |
| `10.cxd5` | `O-O` | +137 cp | +66 cp | 71 |
| `6.e3` | `e4` | +86 cp | +44 cp | 42 |

These particular losses are centipawn differences. When a mate score is present,
`evaluation_loss` uses the synthetic ranking values instead and should not be
displayed as a literal centipawn loss. Scores and rankings can vary with search
budget and engine history; this process retains its search state between moves.
The earlier fresh-engine `Ne5` experiment is therefore not an exact-score oracle
for the game-wide run. These candidates still require human review.

### Building the first practice-and-reveal card

`build_training_card(game, ply_count, *, continuation_san, explanation)` builds
an immutable `TrainingCard` before an actual main-line move. It preserves the
source ply count, pre-move FEN, actual move SAN, prompt, continuation as a tuple
of SAN strings, and explanation. Empty lines, blank explanations, out-of-range
positions, and illegal continuation moves raise `ValueError`.

Selection and explanation are explicit editorial inputs. The builder validates
legal replay; it does not establish that a move is uniquely best, grade an
answer, or automatically turn the largest loss into a puzzle. The returned data
contains the reveal too; the browser initially shows only the prompt and position
and hides the continuation, actual move, and explanation until reveal. This is
visual hiding for practice: someone inspecting the HTML source can see the answer.

For the first card, we selected the position before `16.Ne5`. A separate
500,000-node, three-line Stockfish 19 review found several strong options,
including `Nxg5`, `Ne5`, and `Bxf7+`. We therefore use `Bxf7+` as an illustrative
forcing continuation, without labeling the original `Ne5` a mistake.

This Python example uses the existing fixture and needs no running engine:

```python
import runpy
import chess
from chess_coach.pgn import parse_pgn
from chess_coach.training import build_training_card

game = parse_pgn(runpy.run_path("tests/test_pgn.py")["CHESS_COM_PGN"])
card = build_training_card(
    game, 30,
    continuation_san=("Bxf7+", "Kg7", "Bxe8", "Qxe8"),
    explanation=(
        "Look at forcing checks before quieter moves. Bxf7+ captures a pawn "
        "with check. After the illustrated reply Kg7, Bxe8 captures the rook. "
        "Black can recapture with Qxe8: White has exchanged a bishop for a rook "
        "and a pawn in this line. This is one continuation, not a forced or "
        "unique solution; Ne5 is also a strong option in deeper analysis."
    ),
)

# Show these first.
print(card.prompt)
print(chess.Board(card.position_fen))

# Reveal these after the player has considered the position.
print("Example:", " ".join(card.continuation_san))
print(card.explanation)
```

The full selected line is `16.Bxf7+ Kg7 17.Bxe8 Qxe8`, including Black's
recapture. On 2026-09-15 a manual end-to-end check confirmed that the card's FEN
and original move match a result from the game-wide analyzer, and every move in
the example line replays legally. Automated tests do not assert exact engine
evaluations; see the current validation commands above.
