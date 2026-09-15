# Roadmap to a private chess training app

## First-release goal

Enter a Chess.com username, import recent completed rapid games, see a factual
activity/rating summary, review candidate exercises, practice by playing on the
board, and save reflections. Manual PGN import remains available.

Conversational coaching, learner memory, and adaptive selection follow the first
deployment. Automatic right/wrong grading is not required for this release.

## Current checkpoint

- 3A–3E: domain analysis, reviewed card data, and the local practice page exist.
- 3F: technical browser checks and an editorial usefulness assessment are recorded
  in [VALIDATION.md](VALIDATION.md). A learner's fresh attempt and assessment remain
  a human acceptance gate; automated tests cannot establish teaching effectiveness.
- 4A: reusable command workflow, source/engine provenance, explicit acceptance or
  rejection, and two-game real-engine smoke check implemented. The second bundled
  game is synthetic and is labeled as such.
- 4B: public-API import, bounded sample, factual summary, explicit refresh, cache,
  and selected-game analysis implemented at the command-line boundary. Live import
  and analysis were verified locally. Browser integration is still milestone 6.
- 5: [review checklist](TRAINING_REVIEW.md) and recorded review fields implemented;
  varied real-game teaching-quality validation remains open.
- 6–9: not implemented. Framework, durable storage, access protection, and hosting
  still require explicit decisions. No deployment or public push has occurred.

## 3F — Validate and close the first card

- Attempt the card before revealing the example.
- Check reveal/navigation/reset, preserved drafts, keyboard use, and narrow layouts.
- Record the transferable lesson and what the example does not prove.
- Review and commit the interface; carry board-based move entry into milestone 6.

Done when: the exercise has a usefulness assessment and a clean commit.

## 4A — Process another game without editing application code

- Accept one PGN and explicit player/color selection.
- Analyze, show candidates, and permit manual selection or rejection.
- Preserve source identity, source PGN, exact ply/FEN/move, and engine settings.
- Accept a reviewed continuation and explanation, and generate a practice card.
- Handle invalid input, analysis failure, and no suitable candidate explicitly.

Done when: two different games produce traceable, legally replayable cards through
the same workflow. Command-line tools are an interim adapter, not the final UI.

## 4B — Import by Chess.com username and summarize history

- Fetch public profile, available statistics, and completed-game archives without
  requesting a Chess.com password.
- Identify color automatically, retaining manual PGN fallback.
- Default to 90 days, capped at the newest 100 completed, rated, standard rapid games.
- Show latest reported rapid rating/date separately from sample results, activity,
  and observed rating history.
- Label actual coverage, truncation, missing data, and refresh/check times.
- Suggest the newest five eligible games regardless of outcome; let the user select
  different games. This starting rule does not claim optimal teaching value.
- Bound serial requests, cache responses, deduplicate, support explicit refresh,
  and explain unavailable users, empty histories, API failures, and rate limits.

Done when: a username produces an understandable game list and summary; selected
games enter the same analysis workflow as uploaded PGNs.

## 5 — Establish training-quality rules

- Review clarity, transferability, continuation quality, and relevance.
- Distinguish illustrative lines from forced or unique solutions.
- Consider alternative strong moves; deepen analysis where needed.
- Record acceptance/rejection reasons. Permit no suitable exercise.

Done when: a varied real-game sample produces decisions that can be consistently
defended. Legal continuations and test fixtures alone do not satisfy this gate.

## 6 — Complete the local browser workflow

Define these screens before choosing a framework:

1. Import: username, explicit refresh, or PGN with color selection.
2. History: rating/date, coverage warnings, game list, editable selection.
3. Analysis status: queued/running/completed/failed/cancelled, bounded work.
4. Candidate review: source position, honest evaluations, reviewed line/explanation,
   alternatives, acceptance or rejection.
5. Practice: click/tap and drag move entry, legality and promotion choices;
   **play → explain or skip → reveal reviewed example → explore**.

Bound input size, duration, and concurrency; handle process cleanup and failures.
Do not add automatic grading. A separate worker service is a decision, not a
requirement. Select framework and board library only after reviewing these needs.

Done when: the entire workflow works in a local browser, including failure cases.

## 7 — Save games, cards, and reflections

Choose storage for the private-alpha scope. Save imported games, refresh metadata,
analyses, reviewed card versions, proposed moves, and reflections. Provide history,
deduplication, deletion, and tested backup/restore. Link each attempt to the exact
card version presented. Disposable import caches are not durable training history.

Done when: progress survives restart and a backup can actually be restored.

## 8 — Prepare a reproducible release

Choose private access protection. Package Python, templates, and Stockfish;
verify resource limits, logging, API failure handling, and license obligations.
Keep real-engine integration checks score-independent; add browser smoke checks.
Document configuration, deployment, backup, and rollback. Recheck all safeguards
for a network-exposed service; local command limits are not a production sandbox.

Done when: a clean environment completes the core flow.

## 9 — Deploy and validate the private alpha

Select hosting with engine-process support, persistent storage, and suitable
resource limits. Verify import through saved practice history after deployment.
Test restart persistence, failures, and recovery; record friction and teaching
value across several real practice sessions.

Done when: repeated use needs no terminal intervention and recovery is understood.

## After deployment

- **10 — Conversational coaching:** discuss stated reasoning, ask follow-ups, and
  ground chess claims in verified positions and analysis.
- **11 — Learner memory:** retain relevant statements/corrections; distinguish facts
  from tentative inferences; support inspection, correction, deletion, and tested reuse.
- **12 — History-guided selection:** use reviewed patterns across games and explain
  the evidence behind study recommendations.

“Time at this rating” needs a defined band, observation window, minimum activity,
and missing-history treatment. Stable ratings alone do not prove a weakness or
its cause. Scheduled syncing, rating prediction, and advanced analytics remain
outside the first release.
