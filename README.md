# Chess Training & Analysis

A personal chess training tool that turns completed games into focused practice.

The long-term goal is to help players understand recurring weaknesses in their play, train important positions from their own games, and develop better decision-making habits rather than only viewing engine-best moves.

## Project Status

Early development.

The project is currently focused on building the smallest reliable end-to-end training workflow before expanding features.

## V1 Product Hypothesis

A self-taught intermediate chess player will find training more useful when important positions from their own games are turned into personalized exercises with clear explanations and optional coaching around their original reasoning.

## V1 Scope

The initial version will focus on:

- completed Chess.com rapid games
- exact positions from the player's own games
- identifying meaningful mistakes, misses, and important decisions
- allowing the player to attempt a better move before seeing the answer
- concise explanations of why a stronger move works
- optional deeper coaching and reflection
- remembering training history and recurring weaknesses over time

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

Frameworks, database technology, production chess-engine packaging, frontend stack, AI models, and deployment providers have not yet been finalized. Stockfish is currently used only as a local analysis experiment.

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

## Current Milestone

### Milestone 3 — One End-to-End Training Card

Goal:

Starting from one completed rapid game, produce one usable personalized training position through the real software pipeline.

Completed slices:

- **3A — PGN position retrieval:** parse one PGN, reconstruct its main line, and retrieve the exact position after a requested number of plies.
- **3B — One-move engine comparison:** compare a played move with a Stockfish candidate using a fixed-node, paired MultiPV search and retain explicit centipawn or mate evaluations.
- **3C — Rank player moves:** replay one game, compare the selected color's moves, and return comparisons in descending evaluation-loss order. Ties retain game order.
- **3D — First card data:** build a practice-and-reveal card from an explicitly selected position, preserving its FEN, actual played move, reviewed example continuation, and explanation. Each continuation move is checked for legality.

The next slice is **trying the card through an interface:** display the position,
let the player consider a move and their reasoning, then reveal the example.
The interface technology is still undecided. The highest engine loss is not
automatically the best teaching position.

These slices remain domain-level Python code. No web framework, database, server, training-label thresholds, or AI coaching layer has been added yet.

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
contains the reveal too; a future interface must show the prompt and position
first and withhold the continuation, actual move, and explanation until reveal.

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
the example line replays legally. The automated suite contains 45 tests; it
does not assert exact engine evaluations.
