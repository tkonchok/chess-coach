# Candidate review checklist

An engine ranking proposes places to inspect. It does not decide what to teach.

Before accepting a candidate, record:

1. **Source:** correct game, player, pre-move ply/FEN, actual move, engine version,
   search budget, and perspective. Never use an in-progress game for assistance.
2. **Idea:** one concrete decision the learner can apply elsewhere. Explain the
   mechanism on this board; do not infer their original intention.
3. **Continuation:** legal moves for both sides, including relevant recaptures.
   Name it an illustrative line unless forcing/uniqueness has actually been checked.
4. **Alternatives:** other plausible strong moves and defensive replies. A move
   different from the example is not automatically wrong. Record uncertainties.
5. **Stability:** if ranking or best move changes with search budget, review more
   deeply or decline the position. Preserve any additional review settings/results.
6. **Relevance:** can the learner understand and benefit from this decision? Large
   mate-mapped ranking differences are not literal material counts or cp losses.
7. **Decision:** accept or reject, with a reason. Reject every candidate if needed.

The review JSON includes `decision`, `source_ply_count`, and `reason`. Acceptance
also requires `continuation_san`, `explanation`, and `alternatives`. See `examples/`.
These fields make judgment explicit; their presence cannot establish its quality.
Optional extra review fields, such as deeper-analysis notes, are preserved.

## Current sample assessments

- **Original White card before 16.Ne5:** accept as a forcing-move/exchange-counting
  example, not a “find the only move” puzzle. Include Black's Qxe8 recapture. The
  earlier deeper review found multiple strong moves, including Ne5; do not grade
  Ne5 wrong. The user still needs to assess whether this teaches something useful.
- **Synthetic Black card before 3...Nf6:** accept as a workflow/teaching example of
  noticing Qxf7 mate, blocking the threat while attacking the queen, then meeting
  a renewed threat. Qe7 is another defense worth considering. The continuation
  with g6/Qf3/Nf6 is illustrative. This is not a learner-history diagnosis.
- **Original opening move:** rejection example: no specific lesson has been
  established by its small search difference. Do not turn every ranked move into
  a card (`examples/reject-review.json`).
- **Additional live-import smoke analysis:** the highest-ranked candidate shifted
  from a poor cp evaluation to mate against the player. Treat its large synthetic
  loss cautiously; no reviewed card was published from it. Examine an earlier
  decision and the actual defensive idea before accepting it.

This is a starting rubric, not milestone-5 completion. Review a varied set of
real wins, draws, and losses (both colors and different phases), retain reasons
for disagreements/rejections, and verify that the same standards are applied.
