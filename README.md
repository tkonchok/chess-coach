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

The next slice is **3C — Rank player moves:** walk one game, compare only the selected player's moves, and rank raw evaluation-loss candidates for later human and product review.

These slices remain domain-level Python code. No web framework, database, server, training-label thresholds, or AI coaching layer has been added yet.

Stockfish 19 characterization for the position before `16.Ne5` on 2026-09-09:

| Nodes | Paired best move | Best evaluation | `Ne5` evaluation | Loss |
| ---: | --- | ---: | ---: | ---: |
| 25,000 | `Bxf7+` | +751 cp | +669 cp | 82 cp |
| 100,000 | `Bxf7+` | +780 cp | +653 cp | 127 cp |
| 500,000 | `Bxf7+` | +802 cp | +773 cp | 29 cp |

These are environment-specific observations, not stable expected values or training labels.
