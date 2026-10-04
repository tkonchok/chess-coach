# Validation log

## 2026-10-03 — Archive result filters

Added All results / Wins / Losses / Draws to monthly history browsing. Results use the importing player’s perspective and filtering happens before pagination; navigation retains result, month and time control. No analysis or AI allowance changes.

Performed: 190 default tests discovered, 184 passed, six skipped. Added known-result checks across both colors and a 56-loss two-page sample. Archive Chromium workflow passed (2.403 seconds), checking empty Wins, Losses, preserved filter through three pages, selection and mobile/desktop layout. Whitespace checks passed. Existing public-release gates remain pending.

## 2026-10-03 — Single continuation display and full archive browsing

Removed the duplicate continuation in ordinary exploration/Self analysis. Prepared branches retain an active-ply display; when their UCI sequence equals the saved recommendation, only that display is shown under Recommended line · starting position. Different saved/active lines remain separately labelled.

Added authenticated monthly archive browsing with 50 records per page, All/Rapid/Blitz/Bullet/Daily filters, shared thumbnails/actions, and no 90-day/100-game browsing cutoff. Recent rapid import remains unchanged. Only the current owned archive page is stored as transient import data; selecting analysis persists its source before enqueueing. Completed analyses reopen without reanalysis. No migration or AI request. Standard rated/casual games supported; variants excluded. Existing analysis/storage limits remain, and browse page views have a separate daily allowance.

Performed:
- Default suite: 189 discovered, 183 passed, six skipped (five opt-in browser tests and one pre-existing optional check).
- Four existing Chromium workflows passed after the UI changes, including both-color real-engine practice/save/history, automatic opponent replies, Self analysis single-line visibility, branch labels, promotion, stale commentary and failure handling. The new archive workflow initially found an inaccessible wrapped month label (fixed with explicit labels), then a test-only job-list/detail lookup mistake (corrected). Its targeted rerun passed in 1.892 seconds. All five browser workflows have passing evidence; not claimed as one final all-green invocation.
- Archive browser check covers latest/old month, time-control filtering, 123-game fixture across pages 1–3, selection to a queued job, source survival after leaving the page, and 1280×900/390×844 layouts without horizontal overflow. Inspected the mobile screenshot. Screenshots: generated/archive-1280.png and generated/archive-390.png.
- Backend checks cover old history pagination beyond 100 games, both rated/casual support, malformed records, variants, duplicate records, invalid months/pages/filters, empty index, account isolation of transient sources/thumbnails, persistent selected source, authentication, rate-limit/API failures and unchanged recent importer tests.
- Live read-only Chess.com check for the previously used username found 49 published months; current October 2026 page returned 37 games and oldest August 2020 returned two games, without warnings, using three serial requests and no credentials.
- JavaScript syntax and whitespace checks passed.

Pending public-release gates remain: six-position teaching-quality acceptance, clean Docker verification, production configuration/cost checks, and deployed smoke verification after authorization. No publishing or deployment occurred. Puzzle solve tracking remains separate from saved-attempt “Practiced” semantics.

## 2026-10-03 — Automatic replies beyond prepared lines

Fixed move dispatch after a prepared continuation finishes: clear that finished branch before selecting the live-coach path, so the very next legal move gets an automatic opponent reply while Self analysis is off. Take back removes a user/reply pair in normal coach mode, including outside prepared lines; manual Self analysis and pending-reply recovery still undo one ply. Original proposals and notes remain separate from exploration.

Performed: 184 default tests discovered, 179 passed and five skipped. All four Chromium workflows passed (68.240 seconds), including added checks across both colors for a move immediately after line completion, its automatic reply without selecting another mode, and pair undo. Existing tests cover initial replies, alternative variations, Self analysis manual moves and automatic replies after turning it off, plus save/history and failure handling. JavaScript syntax and whitespace checks passed.

Pending: existing public teaching-quality and deployment gates; this fix does not add puzzle solve tracking or change quotas.

## 2026-10-03 — Explicit Self analysis and automatic coach default

Replaced the Play it through UI action with a Self analysis toggle. Entering it preserves the current path, enables best-move arrows and lets the user move both sides; leaving it returns to automatic live opponent replies. Default first proposal starts coaching automatically again. See recommended line is the explicit branch-reset action. Removed the board's Personal-game practice / Practice with your coach heading block and visible options/privacy dropdown; privacy remains in the coach-header info control. Deprecated manual board-view functions remain development compatibility helpers, not a separate primary mode.

Performed: default suite discovered 184 tests, 179 passed, five skipped. Four Chromium workflows passed. Updated real-game tests exercise automatic first replies, explicit Self analysis without path reset, visible arrows, two manual plies without an automated opponent move, and mode exit followed by a live reply across both colors. Existing reflection/save, history navigation, source/library/layout and failure-fixture checks remain; legacy manual-component checks now select their internal development state directly. JavaScript syntax and whitespace checks passed.

Pending: dedicated pre-proposal Self analysis entry/toggle assertions, additional switching-during-failure fixtures, and existing puzzle-completion/public-release gates. No automatic puzzle solve tracking or new AI grading was added.

## 2026-10-03 — Match encouragement, castling clarity and direct selection

Added concise encouragement for exact engine-line matches and line completion, with a choose-another-puzzle link after the line. Wording acknowledges playing through a line without claiming a graded solve or proven understanding. Original-game moves display their move number and explain O-O/O-O-O as kingside/queenside castling. Removed the redundant primary Practice next position / Practice again link from analysis results; owned position cards and View in Puzzles remain. No progress semantics changed: Practiced still comes from a saved attempt.

Performed: 184 default tests discovered, 179 passed, five skipped. Four Chromium workflow checks passed with direct card selection and continuation-match feedback. Added castling-notation/move-number presentation checks. JavaScript syntax and whitespace checks passed. Pending: independent puzzle-completion tracking/acceptable-answer decision and existing public quality/deployment gates.

## 2026-10-03 — Free self-analysis immediately after proposal

Interactive beta no longer locks legal board entry in the pre-Reveal ready state. Users can play both sides immediately after proposing; subsequent exploration keeps the original proposal separate. Pre-Reveal Take back removes one ply, clearing proposal entry only when returning to the starting position. Explicit Reveal still prepares coaching from the original position and first proposal. Finished coached lines also allow manual exploration without requiring recommended-continuation selection. Existing manual-review/offline behavior is preserved.

Performed: 183 default tests discovered, 178 passed, five skipped. All four Chromium checks passed. Real-game browser tests for both colors now explicitly play an opponent move before Reveal, assert the proposal is unchanged and no walkthrough exists, take back one ply, then enter and complete coached practice. Existing live variation, history navigation, arrows, reflections/save and new library-screen checks remain. JavaScript syntax and whitespace checks passed.

Pending: additional multi-ply and promotion free-analysis browser fixtures, and the separate puzzle-completion decision/public-release gates. Free exploration is not saved or graded.

## 2026-10-03 — Default hints off and separate Reflections

Best-move arrows now start unchecked while live evaluation remains enabled. Added an owned Reflections tab listing non-deleted saved attempts that contain notes or reflection choices; blank attempts remain stored but are omitted. Existing attempts/history URLs remain compatible. Removed saved-note listing from Puzzles and directed reflection-detail/deletion navigation to Reflections. No reflection data was sent to AI or used for training.

Performed: 183 default tests discovered, 178 passed, five skipped. All four Chromium workflows passed, including new default-arrow-off and opt-in-arrow checks. Added reflection filtering/deletion checks; existing ownership, saving and layout checks remain. Whitespace check passed.

Pending: choose the completion rule before implementing puzzle solve tracking independent of reflection saves. Current library badges still mean Practiced based on saved attempts; no solve-grade or completed-puzzle claim has been introduced. Existing public quality/deployment gates remain pending.

## 2026-10-03 — Grouped puzzles, landing and analysis screens

Puzzles groups retained exercise versions by source PGN digest and player color, newest analysis first, with source names/date/result, move-ordered snapshots, practiced/remaining totals and All/To practice/Practiced filters. Only non-deleted saved attempts contribute, once per version; the last deletion removes practiced status without deleting the exercise. Repeated position versions show analysis dates. Empty libraries and empty filters have separate guidance. Analysis results reuse position cards and select the earliest unpracticed position, falling back to Practice again; queued/running/failed/no-result states retain polling and accessible status. Missing imported records fall back to snapshot metadata. Signed-out landing includes a fixed illustrative board/coach preview, a Google entry when configured, a secondary local demo and three workflow steps. No migration, quotas, provider requests or solve grading were added.

Performed: default suite discovered 182 tests, 177 passed, five opt-in tests skipped. All four Chromium checks passed. New tests cover source/color grouping, ordering, retained versions, date/header fallbacks, filters, repeat saves, deletion progress, cross-account library/job access, job states and missing game records. Browser checks cover local landing sign-in entry, queued-to-ready polling, next-position links, group/filter progress, position navigation, 1280 × 900 and 390 × 844 horizontal overflow, plus the existing engine practice/save/retry workflow. Inspected desktop landing/library and mobile analysis screenshots. Visual review found namespace-prefixed inline SVG output rendering incorrectly; fixed namespace serialization and added square/piece DOM assertions rather than weakening checks. JavaScript syntax and whitespace checks passed.

Pending: live Google sign-in on these refreshed screens, comprehensive keyboard/screen-reader audit, broader real-user visual feedback, existing teaching-quality review, Docker and deployed smoke gates. Local browser sign-in uses the explicitly labelled demo, not a live Google assertion.

## 2026-10-03 — Distinguish recommended root and played branch

Labelled the saved recommendation as starting at the original position, and restored the separate active prepared-variation line with branch identity and active-ply marker. Deviated free branches are labelled as separate from that prepared line. Interactive coaching no longer disables/hides the current-position best-move arrow; manual fixed-line review retains its previous highlight behavior. Arrows use current short-search evidence, which can differ from the saved higher-budget recommendation.

Performed: default suite discovered 176 tests, 172 passed, four skipped; JavaScript syntax and whitespace checks passed. All three Chromium workflow checks passed. Pending: reproduce the user's specific h6 position and a dedicated interactive-arrow assertion.

## 2026-10-03 — Reveal pause, readable replies and move history

Moved the updating turn indicator into the coach identity. Proposal entry now waits for explicit Reveal; Take back/Reset to the starting position clears the proposal while preserving notes. Restored the saved recommended engine line separately from the explored branch. Automatic prepared/live replies display the user's position for 900 ms before advancing. Previous/Next review individual plies with a retained current-line timeline; board entry pauses while browsing earlier plies. Take back remains an edit of the line, not a history-navigation action.

Performed: 176 default tests discovered, 172 passed, four skipped. Three Chromium workflows passed with explicit Reveal, a visible recommended line, and Previous/Next path/history assertions for both colors; existing real-engine alternative reply/take-back, narrow layouts and save/retry checks remain. JavaScript syntax and whitespace checks passed.

Pending: dedicated pre-reveal proposal-edit and reset/notes browser assertions, visual timing feedback, and previously recorded public-release gates. The reply pause is deliberate timing, not a new animated-piece renderer.

## 2026-10-03 — Local uncapped exploration and live variation replies

Localhost-only LOCAL_TESTING bypasses daily exploration reservation; public account/global caps stay unchanged. Alternative continuation moves use the owned position-analysis route for a legal Stockfish opponent reply. Returned FEN and move legality are checked before advancing; failures retain the board/notes and offer retry, take back or reset. No new AI requests or strategic narration are added for arbitrary branches. Current short-search evaluations remain White-perspective rather than equal-budget move grading. Take back removes the user/opponent pair (or pending user move), Reset returns to proposal entry, and notes persist. Original move stays visible; navigation is grouped in the coach; turn badge sits by the heading and updates with the actual turn.

Performed: 176 default tests discovered, 172 passed, four opt-in tests skipped. All three Chromium workflows passed. Added local-cap bypass/public-cap preservation coverage. Real Stockfish browser flow explicitly enters an alternative Black continuation, waits for a live reply, takes the pair back and resumes the prepared line; both colors still complete coached practice. Existing manual review, desktop/narrow layout, reflection and save/retry checks remain. JavaScript syntax and whitespace checks passed.

Pending: dedicated live-reply failure/retry and stale-response browser fixtures, automatic underpromotion on a free branch, reset/notes stress checks, user visual review and existing public deployment/teaching-quality gates.

## 2026-10-03 — Automatic coach continuation and analysis reuse

Default beta practice now starts preparation after the proposed move, automatically plays a prepared opponent reply, and accepts the player's continuation on the board. Exact line matches are acknowledged without declaring other legal moves wrong. An alternative stops the prepared sequence, clears its highlights, and offers a recommended continuation, exploration or reflection. Short/terminal lines end normally. Manual review is retained under Practice options; notes and original proposal remain separate from navigation. Added bounded busy-slot retries for live feedback. Import/PGN controls share one panel, existing import controls collapse after import, and the board aligns beneath the heading. Completed game analyses open their existing results rather than consuming another analysis quota.

Performed: 175 default tests discovered, 171 passed, four skipped. All three opt-in Chromium tests passed after fixes. The real-engine browser check now additionally covers automatic replies, exact continuation matches, short-line completion, recommendation comparison and reflection handoff across both colors, with desktop fit and evaluation alignment assertions. Existing manual-review, narrow-layout, promotion, stale-commentary and save/retry checks remain. Targeted test verifies completed-analysis reuse without enqueueing. Inspected the automatic-mode desktop screenshot. JavaScript syntax and git whitespace checks passed.

Pending: deterministic automatic-mode deviation and promotion fixtures, exhaustive automatic preparation failure/stale response checks, user visual review, and previously recorded public teaching-quality/deployment gates. Natural-language accuracy is not established by these interaction checks.

## 2026-10-02 — Board-first coach workspace

Reshaped practice into a larger board/evaluation workspace with one narrower coach column, a persistent knight identity, less nested card styling, shorter prompts and current-step walkthrough text. Reflection and saving stay in the coach column. Existing engine, privacy and persistence behavior is preserved. Reference pages from Chess.com Coach and Lichess training were consulted, but their interactive layout/assets were not fully exposed by the available web reader; this is an original layout guided by the user description.

Performed: 174 default tests discovered, 170 passed, four skipped. Initial Chromium run found board-panel overflow; reduced maximum board size and reran without weakening the assertion. All three browser workflows then passed, covering 1280 × 900 fit, both colors, narrow layouts, full-height evaluation alignment, walkthrough branch navigation, optional reflections and save failure/retry. Inspected desktop coaching/walkthrough screenshots. `git diff --check` passed.

Pending: user visual feedback, full accessibility audit and previously recorded public teaching-quality/deployment gates. Arbitrary free-play conversational commentary and automatic scanning are not implemented by this UI change.

## 2026-10-02 — Personal Puzzles library

Replaced Private history in navigation with Puzzles. Retained exercise snapshots appear as board cards with Ready to try / Revisit states and saved-attempt counts. Saved takeaways remain accessible in a collapsed section; existing history URLs remain compatible. No reflections were deleted, scoring was introduced, or quotas increased.

Performed: 174 default tests discovered, 170 passed, four skipped. All three existing Chromium workflow tests passed. New targeted library checks cover account isolation, retained-position availability and saved-attempt counts. `git diff --check` passed.

Pending: dedicated browser interaction/layout checks for the new Puzzles page, automatic backlog scanning, similar/scored puzzle generation, and the previously recorded public-release quality and deployment gates.

## 2026-10-02 — Game and position previews

Added account-scoped SVG board snapshots to imported games and the practice-position picker. SVG styles are converted to presentation attributes for the existing security policy; internal piece references remain intact. Shortened Games copy and collapsed optional PGN entry and import metadata. Added a UI customization guide with a small accent-color task.

Performed: 173 default tests discovered, 169 passed, four opt-in checks skipped. All three opt-in Chromium tests passed after the template changes, including real Stockfish workflows for both colors and a rendered practice thumbnail. Targeted tests verify both image routes, valid SVG references, conditional requests and cross-account denial even with a matching ETag. `git diff --check` passed.

Pending: dedicated visual review of the imported-game list at multiple widths. The Puzzles replacement, scored/new puzzle generation, and automatic backlog scanning remain scope decisions; no history data was deleted and no scanning limits were raised.

## 2026-10-02 — Narrated paired-line walkthrough

Replaced the prediction UI and separate Request AI explanation button with Play it through, proposed/recommended branch selection, Previous/Next, current-ply narration, referenced-square highlights, and a hover/focus/click/tap information control. Future commentary stays hidden until its ply. Preparation uses the owned card and legal proposed move, matched 50,000-node/0.5-second and 100,000-node/1-second root searches, one Stockfish thread/16 MiB hash, and the shared engine slot with a 12-second process-group deadline. Evidence records both comparisons and engine identity/settings. Successful commentary is cached by version/proposal/evidence/model/prompt; provider requests exclude identity, PGN and reflections. Existing schema/cache storage is reused. Save still retains the original proposal and notes, not navigation state. Live short-search evaluation continues independently; arrows pause in the fixed-line view in favor of cited-square highlights.

Performed: default suite discovered 172 tests, 168 passed, four opt-in checks skipped. All three opt-in Chromium tests passed. Actual Stockfish browser workflows cover both colors, preparing both branches, stepping to the end, branch resets, original-proposal preservation, full-height evaluation alignment, no page/board-panel scrolling at 1280 × 900, optional reflections, save failure/retry and history. Controlled browser fixtures additionally cover preparation failure/retry, promotion, backward navigation, provider latency without navigation locking, stale commentary after leaving, automatic commentary request field allowlist, exact current-ply/future-hidden text, keyboard navigation, hover/focus/Escape/touch information access and 390px layout. Offline keyboard underpromotion/reveal still passes. Domain/route tests cover score perspective, matched budgets, identical roots, uncertain ranking, illegal roots, en passant/check/promotion/direct attacks, early draw termination, commentary coverage/references, privacy, CSRF/ownership, cache reuse, timeout/quota fallback and public quality gating. Supervisor checks verify the 12-second shared-slot protocol. Desktop walkthrough screenshots inspected. `git diff --check` passes.

Six real-game positions (three per color) were reviewed as engine-fact walkthroughs: 64 steps legally replayed with factual event inspection. **AI teaching-quality acceptance failed:** the initial six provider attempts produced one rejected-reference bundle and five HTTP 429 responses; two tighter-prompt retries of the rejected position also failed reference checks. Raw prose included uncited threats and unsupported safety/outpost wording. These rejected bundles were not shown. See TEACHING_REVIEW.md for the per-position record and remaining limits. Public `WALKTHROUGH_AI_ENABLED` remains off by default; localhost testing is preview only. No provider purchases were made.

Pending: accepted live AI commentary across the six-position teaching set, human teaching-quality sign-off, the user smoke check after server restart, broader device/load checks and existing OAuth/Docker/deployment release gates. This verifies interaction and failure handling, not teaching effectiveness or public readiness.

## 2026-10-02 — Guided exploration with a companion

Implemented a static knight guide for the proposed-move branch: legal prediction or Skip via Show the reply, reveal a matching legal engine reply, explicit Play reply, then continue the player's move for at most three opponent replies. Predictions are separate from the branch and are not graded or saved. Original proposals, reflections and takeaway drafts remain intact. Reset/undo/comparison exit guided mode; engine failures offer Retry or ordinary exploration. The meter now matches the square board height on its right edge, neutral before Reveal and during prediction. Captures, checks, promotion and material changes are factual board-derived events, not generated strategic explanations. No external AI requests, public endpoints or database schema changes were added.

Performed: default suite discovered 164 tests, 160 passed, four opt-in checks skipped. All three opt-in Chromium tests passed. Two real-game fixtures with actual Stockfish complete the three-reply sequence for both colors, test legal keyboard prediction and skipped predictions, hide feedback during prediction, show reply arrows, compare/restart branches, preserve the original proposal, then save/retry/reopen history. A controlled promotion card and fixture engine HTTP responses verify underpromotion predictions, 503 failure and retry, preserved takeaway drafts, late aborted replies after branch switching, early insufficient-material draw and reflection navigation. Known material result after queen promotion is White 0/Black 9, Black change +8. Desktop checks assert no page/board-panel scrolling at 1280 × 900; desktop and 390px mobile checks assert full-height bar alignment and no horizontal page overflow. Existing offline keyboard promotion/reveal/navigation still pass. Inspected generated White/Black guided screenshots. `git diff --check` passes.

Pending: user check in the restarted local authenticated app, six-position teaching-quality review, broader device/load checks and the existing public deployment gates. This change establishes interaction behavior, not improved visualization or playing strength.

## 2026-10-02 — Live exploration and compact practice

Added authenticated, CSRF-protected position analysis from the owned exercise and a legally replayed move path. One shared engine lock prevents overlap with full-game analysis. Short searches use one Stockfish thread, 16 MiB hash, 25,000 nodes/0.35 seconds and a five-second subprocess deadline. Terminal positions require no engine. Client feedback starts after Reveal, caches bounded FEN results, ignores stale responses and shows approximate White-perspective scores, a bar, legal continuation and optional best-move arrow. Coaching and reflection/save tabs keep the desktop workspace compact; smaller screens scroll and unusually long coaching content can scroll within its panel.

Performed: default suite discovered 163 tests, 160 passed, three opt-in checks skipped. Tests cover known score perspective on both turns, mate/draw handling, illegal engine lines and input moves, cross-account route isolation, busy-slot rejection without usage consumption, timeout process-group cleanup and quota error/lock preservation. Both opt-in Chromium tests passed with actual Stockfish: two real-game fixtures complete analysis, reveal, live arrows for both sides, arrow toggle, optional reflections, save failure/retry and history; the offline browser test covers keyboard promotion and navigation. Desktop assertions verify no page or board-panel overflow at 1280 × 900; existing narrow-layout checks pass. Screenshots inspected under `generated/compact-white-coaching.png` and corresponding Black/reflection outputs. `git diff --check` passes.

Pending: user check against the restarted Google-authenticated server, broader desktop sizes, load testing, live multi-account OAuth verification, the six-position coaching-quality gate, Docker and deployment checks. No claim of public release readiness is made.

## 2026-10-02 — Identify exhausted import allowance

The local account had one analysis, five imports, zero AI requests and no active job. The five-import default, unchanged by the earlier local analysis override, caused the reported generic quota error. Extended explicit localhost testing mode to 20 imports/account/day; public imports remain five, global imports 100, and analysis/queue caps are unchanged. Quota errors now name the action, exhausted account/global limit, and 00:00 UTC reset time. No history, usage counters or credentials were changed.

Default suite: 157 discovered, 154 passed, three opt-in checks skipped. A focused route test demonstrates five accepted failed imports consume the public allowance, the next request produces a specific quota message, and localhost testing accepts another request using the same existing count. The non-reloading server must restart with `.env` sourced; no browser run was repeated for this backend-only limit change.


## 2026-10-02 — Stitch-inspired interface pass

Read the supplied `DESIGN.md`, HTML and screenshot as design references. Adopted the cream/forest palette, rounded panels, navigation pills, large framed board and reflection chips using the existing Flask templates and local CSS. No CDN scripts/fonts or additional frontend dependencies were introduced. Preserved legal move entry, optional notes, engine-only fallback and transactional saving; no unique-solution/strong-move grading or device-only storage claim was copied from the mockup.

Board ranks/files now sit outside the squares and reverse for Black. Reflection choices use unselected native radio controls with visible focus and a Skip action, synchronized to the existing save contract. Source/version identifiers live in an expandable footer section. History uses readable session cards; saved proposed moves display SAN rather than UCI coordinates, reconstructed from the exact stored exercise.

Checks: default suite 156 discovered, 153 passed, three opt-in checks skipped. Actual Chromium two tests passed, exercising two real-game workflows, both label orientations, white/black knight computed fills, click and keyboard entry/promotion, keyboard reflection selection/Skip, saved reflection detail, save failure/retry, Try again and 390-pixel layouts. Desktop and narrow-layout screenshots were visually inspected. JavaScript syntax and diff whitespace checks passed. Local screenshot artifacts include `generated/stitch-practice-white-desktop.png`, `generated/stitch-practice-black-desktop.png`, and the existing mobile screenshots.

Required for this visual slice: applied reference styling, outside coordinates, accessible optional choices and working save/revisit — complete. Optional follow-ups: board flip, source-game context and direct next-position navigation. Broader UX, live coaching teaching review and deployment remain separate pending release work. The mockup is inspiration; this is not a pixel-exact reproduction or a completed usability study.


## 2026-10-02 — Local analysis testing allowance

User encountered the intended one-analysis/day beta cap while testing more games. Added explicit `LOCAL_TESTING=1` in private local configuration, allowing 20 analyses/account/UTC day only on localhost. Public origins reject this mode and default to one. The global cap of 30, one active job/user and three queued jobs remain unchanged; no usage records or sessions were deleted. Tests confirm a second local analysis after completion is accepted, concurrent work is still rejected, and public configuration fails closed. Default suite: 156 discovered, 153 passed, three opt-in checks skipped.

Also removed a real-looking Groq key from `.env.example`; the template must contain placeholders only. The key was inadvertently exposed in local diagnostic output and should be revoked/replaced privately. No key value is recorded in this validation log. Existing private `.env` credentials were preserved; publication has not occurred.


## 2026-10-02 — Piece rendering and live Groq failure fixes

User reported ambiguous piece colors, immediate coaching fallback and apparently working session saving. Python-chess knight paths used inline fill/stroke styles, blocked by the existing CSP; converted trusted SVG styles to presentation attributes, keeping CSP restrictions. Actual Chromium checks confirm solid white/black knight fills, all template assets free of inline styles, narrow layouts, promotion/navigation and two real-game save/history flows.

The local Groq key was configured; it was never printed. A positions-only synthetic evidence request reproduced HTTP 403/error 1010 with the default Python urllib user agent. Adding an explicit `ChessCoach/0.1` header produced a successful live structured response and passed move-reference validation. This establishes connectivity, not chess teaching quality: synthetic evaluations are not real engine evidence, and no quality approval is claimed.

The account's local daily AI allowance had reached five requests with no successful cached explanation. Performed a one-time local repair only when exactly one current-day AI usage row was at five and the explanation cache was empty, restoring its count to zero. The configured daily caps remain unchanged; no reset endpoint was added and no attempts/notes were altered.

Fallback now distinguishes missing configuration, application quota, provider quota, rejected credentials, blocked requests, connection/timeout, and invalid responses; no raw provider errors or secrets are returned to the browser. Engine-only practice and saving remain usable.

Checks: default suite 154 discovered, 151 passed, three opt-in checks skipped; actual Chromium two tests passed (including piece computed fills and existing retry/history flows). JavaScript syntax and diff whitespace checks passed. The user's non-reloading server needs restarting; live coaching on an actual exercise and the six-position teaching review remain pending.


## 2026-10-02 — Live import certificate fix

User confirmed real Google sign-in works, then reported the generic import error. A direct request using the original importer reproduced Python's `CERTIFICATE_VERIFY_FAILED` (missing local issuer roots). Added the already-installed certifi trust bundle as an explicit pinned dependency and configured urllib HTTPS handlers for Chess.com and Groq. Certificate and hostname verification remain enabled; redirects remain disabled. This is application-local and does not modify system certificate settings.

A live Chess.com profile request now returns HTTP 200 with verified TLS. A full bounded import for the previously used public account completed with 100 eligible games, seven requests and no coverage warnings; its disposable cache was removed automatically. Import error pages now distinguish missing usernames/archives, provider rate limits, TLS verification, connection failures and other bad responses. Default suite: 151 discovered, 148 passed, three opt-in checks skipped. New tests verify a populated CA context with hostname/certificate checks and error categories. `pip check` and `git diff --check` passed. The user must restart the non-reloading server to load the fix; actual user-browser retry and live Groq coaching remain pending.


## 2026-10-02 — Browser beta implementation (local, not deployed)

Preserved the existing uncommitted prototype work. Reused the CLI/domain comparison, importer, board and manual snapshots; added the beta adapter, explicit SQLite schema, immutable automatic snapshots, supervision, quotas, coaching adapter and history. No commit, push, purchase or external publication was performed.

Checks actually performed:

- Default suite: **148 discovered, 145 passed, 3 opt-in tests skipped**. Known comparison fixtures verify mover score perspective and paired results. Failure cases cover unstable recommendations (including changes during continuation search), no candidates, malformed sources/PGNs, snapshot tampering, provider output errors/timeouts/quota fallback, queue quotas, spawn/timeout cleanup and restart interruption.
- Real Stockfish CLI integration: **one test passed**, covering both original bundled examples (one is synthetic). Local Stockfish 19; existing python-chess asyncio deprecation warnings are non-failing.
- Actual Chromium: **two tests passed**. One covers two anonymized real games with real Stockfish, selected-game browser analysis, optional reflection, missing-provider fallback, induced save failure/retry, private history, Try again and 390-pixel layout. White uses PGN fallback; Black uses a fixed importer response to exercise username input and game selection without external API variability. The second covers keyboard selection, promotion cancellation/reopening, knight underpromotion, reveal and previous/next navigation. It exposed a queued dialog-close race, which was fixed and rerun successfully. This is not live Google authentication or a live Chess.com import.
- Privacy/ownership tests: second account receives 404 for another account's exercise, game analysis, job/status, attempt and deletion; mutation requests require CSRF. Unicode notes remain escaped. Mocked OAuth success/failure verifies the adapter's session behavior, not actual provider cryptography or consent.
- Captured coaching payload allowlist excludes identity, original PGN and injected reflection fields. Successful explanation cache avoids repeated provider requests; exhausted AI allowance retains engine reveal/save. No live Groq output was obtained.
- Transactional saves: concurrent identical submission returns the same completion timestamp and one attempt; a changed payload conflicts. Deleted attempt tombstones prevent retry resurrection. Fresh Store reopens history; SQLite backup restores into a separate database with the same exercise/notes.
- Five previously imported real-game reports produced 11 automatic positions at 100,000/200,000 nodes in an exploratory run. Source snapshots and legal continuation reconstruction passed; this preceded the final continuation-root stability tightening. These outputs are candidates, not teaching approvals.
- `pip check`, JavaScript syntax checks and `git diff --check` passed. Narrow-layout screenshots were visually inspected for both colors. Local browser recordings/screenshots are under ignored `generated/`; not published.

Pending release acceptance:

- At least six positions across both colors reviewed for natural-language accuracy, uncertainty and usefulness with actual provider output. See TEACHING_REVIEW.md. `AUTOMATIC_EXERCISES_ENABLED` defaults off until this gate passes.
- Real Google sign-in/state failure/logout with two actual accounts; live username import through the browser and Groq free-account/model availability. Credentials were absent during implementation; setup is in CREDENTIAL_SETUP.md.
- Docker build and clean workflow with Python 3.13/Linux limits, exact packaged Stockfish version and volume permissions. Docker is absent locally. No container or deployed smoke check is claimed.
- Dependency/distribution license requirements and project-license decision, off-volume backup operations, Railway cost controls/usage measurement, and authorized deployment.
- Actual drag interaction and extended browser assistive-technology testing remain pending; click and keyboard entry have been exercised. No independent security, load or teaching-effectiveness audit has been performed.


## 2026-09-24 — Project-direction handoff reconciliation

Inspected current AGENTS.md, README, roadmap, validation/review notes, domain/web/
CLI/import boundaries, tests and uncommitted diff. Found 10 modified tracked files
before this pass; preserved the existing reviewed-snapshot loader and optional UI
changes. Current local HEAD is `0e799f9` (interactive practice board). Historical
commit references below are dated records, not a claim about current HEAD.

Fresh checks actually run:

- `.venv/bin/python -m unittest discover -s tests`: 108 discovered, 107 passed,
  one real-engine test skipped as intended.
- `RUN_STOCKFISH_TESTS=1 .venv/bin/python -m unittest discover -s tests -p
  'test_integration.py' -v`: one integration test passed, exercising both bundled
  games with real Stockfish; one fixture is deliberately synthetic. Existing
  python-chess asyncio deprecation warning is non-failing.
- `pip check`: no broken requirements. Pip cache permission warning is non-failing.
- `node --check chess_coach/static/practice.js` and `git diff --check`: passed.
- Available interpreter: Python 3.14.6; `sqlite3` import reports SQLite 3.50.4.

Discrepancies/planning changes:

- SQLite is now approved, superseding documentation that storage is undecided.
- Finish still only reveals a message; no persistence/history exists. Snapshot
  loading works, but the web adapter drops full snapshot/version data after load.
  The card-content ID is not the complete review-version ID. Default demo cards
  lack an accepted analysis snapshot; do not manufacture provenance for them.
- Existing snapshots already contain source PGN and review content: reuse them,
  rather than invent another digest-only reference scheme.
- Three optional note concepts remain distinct. An unanswered field is not the
  same as explicitly not remembering. The older domain/offline prompt still asks
  for explanation, whereas the interactive UI no longer requires it.
- Updated README/roadmap and added ATTEMPT_STORAGE.md as a proposed, staged design.
  Asked which first-release boundary the user wants; baseline remains unchanged
  pending an answer. Saving history is not adaptive coaching.

No application code, dependency, database, commit, push or deployment was created
by this reconciliation. No browser/live Chess.com check was repeated this turn;
prior manual observations remain dated above/below. Storage tests, browser saves,
restart/history persistence and recovery are still pending implementation.

## 2026-09-24 — Optional-reflection practice flow

- Original game move is visible before retry; the board remains at its pre-move
  position. Original-game and new-attempt notes use separate optional expanders.
- The board is playable without answering a prompt. Reveal needs a proposed move,
  not a written explanation or explicit skip. No move grading was introduced.
- "I don't remember" preserves any draft but marks it as not recalled reasoning.
  Both pre-reveal fields and this choice lock on reveal; takeaway stays editable.
- A new HTML contract test was observed failing before implementation. It checks
  distinct optional controls and direct reveal, not JavaScript execution.
- Manual Firefox checks on a separate localhost test tab: blank-note play/reveal;
  original-note draft plus "I don't remember"; read-only draft rejects typing;
  separate attempt note; reset before reveal preserves drafts and choice; reveal
  still works after reset; attempt note rejects typing after reveal; example Next
  and reset preserve all three notes; finish works. Reveal gets keyboard focus
  after proposing a move instead of forcing focus into a writing field.
- These changes do not save notes across reloads or send them to an AI. Browser
  checks are manual, not an automated browser regression suite. Narrow-screen and
  full screen-reader checks have not been repeated for this slice.

## Saved-review practice adapter checkpoint

- `card_from_review()` checks supported/accepted snapshots, their version digest,
  and consistency with source PGN and editorial review. Reuses `review_candidate()`
  without engine analysis, leaves input unchanged, and restores immutable moves.
- `create_app_from_review()` reads at most 25,000,001 bytes to enforce a
  25,000,000-byte limit before decoding UTF-8/JSON. Missing, oversized, malformed,
  inconsistent, and rejected files fail rather than loading a default card.
- Regression tests first reproduced silent truncation and missing identity labels,
  then passed after correction. Tests use temporary files and controlled analysis
  results for both bundled games; they also check the exact size boundary.
- Flask startup (`routes`) succeeded for both existing generated accepted reviews.
  Test-client requests verified the White and Black starting positions and legal
  replay of `16. Bxf7+ Kg7 17. Bxe8 Qxe8` and `3...g6 4. Qf3 Nf6` respectively.
  The existing rejected review failed with an explicit accepted-reviews-only error.
  No live practice page was restarted or reloaded for these checks.
- Full suite: **106 tests passed**, including real Stockfish integration.
  Dependency and whitespace checks passed; the existing asyncio warning remains.

After the earlier computer-control interruption, the user reported successful
keyboard board entry, example navigation/proposal restoration, and narrow-window
layout checks. Inspection had also shown reset preserving the original reasoning
and separate takeaway. These are manual reports, not automated browser coverage.
Promotion-dialog interaction, skip, touch hardware, and a full accessibility audit
still need dedicated checks.

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
