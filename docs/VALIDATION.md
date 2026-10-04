# Release validation — 2026-10-03

## Performed

- Default suite: 191 discovered, 185 passed, six opt-in checks skipped.
- Local real-engine suite before the health-host regression: 190 discovered, 185 passed, five browser checks skipped. Stockfish 19 / Python 3.14.
- All five Chromium workflows passed in one invocation (70.426 seconds): archive/result filters, both-color practice/save/retry, promotion, stale responses, failure fallback, library navigation and desktop/mobile layouts.
- Built the production Docker image with Python 3.13 and Debian Stockfish 15.1-4. Its verification image ran 191 checks: 186 passed, five browser checks skipped. CLI now honors STOCKFISH_PATH.
- Actual Chromium against the running production container: both anonymized PGNs analyzed; automatic opponent replies, Self analysis, default-hidden arrows, optional reflection saving and 1280×900/390×844 no-overflow checks passed. The fixtures yielded one accepted position each at the shipped engine budget.
- Container /health returns 200; the regression test accepts Railway's probe hostname and rejects an unknown host.
- Docker retains the exact Stockfish package version, Debian copyright notice and matching .dsc/original/Debian source archives. Development examples and tests are excluded from the production image.
- Credential-pattern scan: 89 working-tree release files and 111 original history blobs, no credential matches. Real names in the example PGN were anonymized; original history needs equivalent public-copy sanitization before pushing. Environment files, local databases and generated recordings are ignored. This is a targeted scan, not a security audit.
- JavaScript syntax, dependency consistency and whitespace checks passed.

## Additional release checks performed

- Six freshly selected positions, three per color: exact-version validation, legal replay, factual capture/check/promotion/material/attack cross-checks, both-branch browser rendering and board/bar alignment passed with Stockfish 15.1-4. See the bounded, AI-assisted review in TEACHING_REVIEW.md; it does not approve generated strategic prose.
- Actual Stockfish was observed before a scaled 0.2-second supervisor timeout. The job failed and no Stockfish children remained afterward. Running durable jobs became failed on recovery. The public configured deadline remains 240 seconds; a full four-minute wait was not performed.
- Two saved attempts survived container replacement with the same test volume/session configuration. SQLite backup restored into a separate database with both attempts intact.
- The final five-browser suite passed after the reply-status correction (73.479 seconds).
- Public history scan: 117 blobs, no configured-secret/token-pattern, historical example-name or excluded-data matches. Published author/committer emails use the GitHub noreply address. Original local history is preserved on codex/release-v1 and codex/original-main; only sanitized main was pushed.
- GitHub repository published as tkonchok/chess-coach, public/default main. CI passed: https://github.com/tkonchok/chess-coach/actions/runs/37178324658.

## Pending deployment checks

Railway app installation/repository authorization, Full Trial networking, volume/HTTPS/private secrets/cost configuration, deployed workflow with two real Google accounts, and deployed restart persistence. Do not claim a deployed v1 until these pass.

AI teaching-quality review previously failed. Keep WALKTHROUGH_AI_ENABLED=0 publicly and do not configure a provider key for the engine-only release.

[Earlier detailed evidence](archive/VALIDATION_HISTORY.md) preserves previous performed checks and their limitations.
