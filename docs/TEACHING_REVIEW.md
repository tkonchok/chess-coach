# Teaching-quality release gate

Automatic preparation is implemented. The engine-fact release review below passed six positions across both colors; generated AI commentary remains blocked by its separate failed review. No editorial approval is inferred from engine output. The rows below are review candidates, not accepted lessons. These local output files are ignored and are not a permanent public dataset.

## Required review

For each position, replay the continuation and alternatives; check score perspective and both comparisons. For an AI-enabled release, also review the actual provider explanation for accuracy, uncertainty and usefulness. Identify unsupported claims about threats, forced outcomes, intentions or uniqueness. Decide whether the lesson gives a practical transferable idea. A legal line alone is insufficient. If positions fail, tighten selection and rerun; do not lower this gate.

The initial implementation had no Groq credentials. Later connectivity and the walkthrough sample attempts below were performed; teaching-quality acceptance remains pending. Structured-output support for the default model was checked against [Groq documentation](https://console.groq.com/docs/structured-outputs); it cannot establish explanation accuracy or free account availability.

## Candidate worksheet

| Side | Source / ply | Version | Recommended / played | Verified loss | Review |
|---|---|---|---|---:|---|
| white | c1d3ad31d549 / 26 | 31392b5054c9 | Bxe4 / Ng3 | 387 cp | Pending |
| white | 840cb0da48ec / 34 | 631fba062ba3 | Nf3 / Ne6 | 637 cp | Pending |
| white | 840cb0da48ec / 38 | 6293bb26d87b | Ba4 / Rab1 | 627 cp | Pending |
| black | 55d497077e35 / 27 | 827d56ec1855 | f5 / fxe5 | 349 cp | Pending |
| black | 55d497077e35 / 31 | eff8776ab847 | Nb3 / Bxe5 | 380 cp | Pending |
| black | 55d497077e35 / 23 | 54093fca1ff2 | Bd7 / f6 | 256 cp | Pending |

These candidates came from five real previously imported game reports at 100,000/200,000 nodes, Stockfish 19 locally. After further selection changes, regenerate candidates before signing off. Browser checks use separate anonymized real-game fixtures and demonstrate interaction, not teaching quality.

Review record per position: engine/version/budgets, legal replay result, actual explanation, factual issues, uncertainty, transferable suggestion, reviewer/date and accept/reject rationale. Keep original evidence so rejection or future reanalysis cannot rewrite past review.

## 2026-10-02 — Narrated walkthrough review

**Result: AI teaching-quality gate failed; do not enable public AI walkthroughs.** The engine-fact UI remains available. Local `LOCAL_TESTING=1` permits preview, not editorial approval. `WALKTHROUGH_AI_ENABLED` defaults to 0 publicly.

Six prepared positions, three per color, were legally replayed and their mechanically derived capture/check/promotion/direct-attack facts inspected: 64 steps total. Sources are the two anonymized real-game browser fixtures and previously prepared local real-game exercise snapshots. Existing exercise selection thresholds were not weakened. Root comparisons use matching 50,000-node/0.5-second and 100,000-node/1-second caps, with mover-perspective scores. Recorded Stockfish settings are one thread and 16 MiB hash.

| Position | Your/original move versus recommendation | Factual visual consequence reviewed | Provider result |
|---|---|---|---|
| White 1 | Ng3 / Bxe4 | Played branch trades knights on g3; recommendation removes the knight on e4 and shows the bishop recapture. | Initial request rate-limited; AI accuracy pending |
| White 2 | Ne6 / Nf3 | Played branch continues through Bxe6, Qxe6 and a later Nxc2 bishop capture. | Initial request rate-limited; AI accuracy pending |
| White 3 | Rab1 / Ba4 | Played branch shows Nd4 and a later bishop capture on c2; the alternative starts by moving that bishop to a4. | Initial request rate-limited; AI accuracy pending |
| Black 1 | O-O / dxc4 | Played branch permits Nxe6; alternative begins with the capture on c4 and illustrates a queen exchange. | Rejected move/square references on three attempts; wording review failed |
| Black 2 | fxe5 / f5 | Played branch shows Nxe5 and a subsequent knight move to g6; alternative keeps a different pawn placement. | Initial request rate-limited; AI accuracy pending |
| Black 3 | Bxe5 / Nb3 | Played branch includes Bh5+ and Qxf6; alternative illustrates the knight/bishop exchange on b3. | Initial request rate-limited; AI accuracy pending |

The first provider pass attempted all six bundles: one response failed reference checks and five returned HTTP 429. Two tightened-prompt retries of Black 1 were also rejected. Raw local samples used long move notation without valid references or mentioned uncited squares/threats. Sample prose also labelled castling “safe,” inferred an outpost, and called an independent capture a recapture. Structure/reference checks caught these bundles; they cannot catch all semantic chess errors. None of those rejected sentences are presented as accepted coaching.

Evidence and rejected raw samples are in ignored `generated/walkthrough-review/`. The current prompt is `walkthrough-v2`, with compact evidence, exact SAN/cited-square instructions and short salient-fact commentary. This is a tightening step, not proof of quality. Broader live samples and a human teaching-quality sign-off remain required before public enablement. Provider rate limits are a separate availability constraint; [Groq rate-limit documentation](https://console.groq.com/docs/rate-limits) publishes per-minute token limits, so review requests must be paced. No paid provider tier was activated.

## 2026-10-03 — Engine-fact release review

Six freshly selected positions across both colors were reviewed with the distributed Debian Stockfish **15.1-4**, one thread/16 MiB hash. Selection retained the original 100,000/200,000-node thresholds and stable recommendations. Paired walkthrough roots used matching 50,000-node/0.5-second and 100,000-node/1-second budgets. No provider requests were made.

| Side | Original / recommendation | Verified loss | Demonstrated consequence and usefulness |
|---|---|---:|---|
| Black | fxe5 / f5 | 312 cp | The original branch includes Ng6 and Nxh8+, making the rook capture and check visible. The alternative has a different pawn placement; no forced-win claim. |
| Black | Be4 / c4 | 340 cp | Bxe4 captures the moved bishop; c4 attacks the bishop on d3 and the alternative shows Bf5+. Useful for inspecting forcing captures and checks. |
| Black | Bd6 / Bxa1 | 162 cp | Bxa1 captures a rook and Qxa1 captures the bishop. The displayed events let the learner see the exchange rather than infer it from the evaluation alone. |
| White | Ng3 / Bxe4 | 240 cp | Nxg3/fxg3 changes the pawn placement; Bxe4/dxe4 exchanges the pieces on e4. Both branches accurately identify the captured pieces. |
| White | Ne6 / Nf3 | 504 cp | The original line reaches Bxe6, Qxe6 and Nxc2; the bishop on c2 is captured. The short alternative is illustrative and does not prove a forced saving sequence. |
| White | Rab1 / Ba4 | 430 cp | The original line shows Nd4 attacking the queen and Nxc2 capturing the bishop; Ba4 moves that bishop first. The coach describes attacks/captures, not a trapped bishop. |

Review method: AI-assisted factual/code review, exact snapshot validation, legal replay of every ply, and cross-checks of captures, checks, promotions, material deltas and direct-attack references against the board. Both root comparison rankings stayed consistent in these samples. This is acceptance of bounded **engine-fact coaching**, not human editorial approval or acceptance of generated strategic explanations. The fallback is useful for visualizing demonstrated events but remains limited on quiet moves and short PVs. No selection rule was weakened.

Original private game reports were anonymized before regeneration. Full evidence stays in ignored `generated/release-review/`. Public AI remains disabled; its separate failed review above is unchanged. An independent chess teaching review remains useful before making stronger coaching claims.
