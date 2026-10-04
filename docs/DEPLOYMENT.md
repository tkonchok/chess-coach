# Deployment runbook — not yet performed

Do not publish until the teaching-quality gate, live identity checks and clean-container workflow pass. Purchases and deployment require the owner's explicit authorization. The $10–15 monthly target is a budget estimate, not measured usage.

## Local container check

Docker Desktop is installed and the image build/local automated checks passed on 2026-10-03. Use the following commands to reproduce; deployed checks remain pending.

```sh
docker build -t chess-coach-beta .
docker volume create chess-coach-beta-data
docker run --rm -p 8080:8080 --mount source=chess-coach-beta-data,target=/data --env-file .env.docker chess-coach-beta
```

Create an ignored `.env.docker` with `APP_ORIGIN=http://127.0.0.1:8080`, `LOCAL_DEMO=1`, a random `SECRET_KEY`, and `AUTOMATIC_EXERCISES_ENABLED=1` for local evaluation. Verify `/health`, two game-to-history flows, shutdown during analysis, restart history, volume permissions and a separate backup restore. The image uses Python 3.13; local tests used Python 3.14, so the container check is essential.

## Railway — owner-authorized trial deployment

1. Create one application service from the Dockerfile and one persistent volume mounted at `/data`. Keep one replica, one Gunicorn worker and eight threads; do not enable preloading. Health path is `/health`. Stockfish is installed in the image at `/usr/games/stockfish`.
2. Generate the Railway HTTPS address. Set `APP_ORIGIN` to that exact origin without trailing path, `DATABASE=/data/chess-coach.sqlite3`, and a persistent random `SECRET_KEY` of at least 32 characters. Generate locally using `python3 -c "import secrets; print(secrets.token_hex(32))"`; enter it privately in platform variables. Never commit it.
3. Set `LOCAL_DEMO=0` and `LOCAL_TESTING=0`. Set `AUTOMATIC_EXERCISES_ENABLED=0` until the documented teaching review passes. Enter `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, leave `GROQ_API_KEY` unset for the engine-only public release, and set `WALKTHROUGH_AI_ENABLED=0` privately as environment variables.
4. Configure a Google OAuth web client and consent screen/test users. Authorized callback must exactly equal `APP_ORIGIN/auth/google/callback`. Verify login, callback failure, logout and two real Google accounts. Do not assume the mocked callback test proves provider integration.
5. Verify volume ownership before accepting traffic. Railway documents root-mounted volumes and `RAILWAY_RUN_UID=0` for images with a non-root user. This is a platform configuration tradeoff requiring a clean smoke check; the image itself defaults to user `coach`. See [Railway volume permissions](https://docs.railway.com/volumes).
6. Configure compute usage alerts and an owner-approved hard spending cap before publication. Hard caps can take workloads offline. Review all workspace projects because hosting another project contributes to the budget. See [Railway cost controls](https://docs.railway.com/pricing/cost-control). Measure actual CPU, RAM, storage and analysis duration before calling the estimate reliable.
7. Verify `/health`, username import, analysis, practice, engine-fact coaching, retry-safe save, history, deletion, account isolation and restart persistence on the deployed address. Record date, build and outcomes in the validation log. Only then enable automatic exercises after their separate quality approval.

The app disables Gunicorn access logging and never logs request bodies or note content. Platform proxy logging should also be reviewed. Existing SQLite data and backups include private notes; restrict access and never upload them to a public repository.

## Backup and restore

Use SQLite's backup API rather than copying a database during writes. Run these commands inside the environment containing the volume, then transfer the backup to private storage outside that volume:

```sh
.venv/bin/python -m chess_coach.backup backup instance/chess-coach.sqlite3 /private/tmp/chess-coach-backup.sqlite3
.venv/bin/python -m chess_coach.backup restore /private/tmp/chess-coach-backup.sqlite3 /private/tmp/chess-coach-restored.sqlite3
```

Inside the image use `python` and `/data/chess-coach.sqlite3`. Destinations must be new files. Restore verifies SQLite integrity and schema version; the test suite also reopens saved attempts from the separate restored database. Keep the original database until the restored installation is verified. Stop the service before replacing its configured database path. Daily off-volume backup scheduling and retention need an operational decision before accepting important user data.

## Troubleshooting

Missing Stockfish fails the job without a partial exercise. An interrupted running job becomes failed on restart. A queued job remains queued. Daily allowances use UTC and accepted failures count; no suitable positions is a legitimate completed result. A second Gunicorn worker/instance sharing storage is rejected by the supervisor lock. Missing AI credentials leave the engine line usable. Missing Google credentials show a configuration message; public demo login cannot substitute for authentication.

## Walkthrough commentary gate

Keep `WALKTHROUGH_AI_ENABLED=0` in public hosting until six-position teaching-quality acceptance. `LOCAL_TESTING=1` permits local preview only and is prohibited on public origins. Walkthroughs remain available with board-fact commentary when Groq is unavailable, quota limited, or invalid. One prepared bundle consumes an exploration allowance (including cached preparation); one uncached AI bundle consumes an AI allowance. Budget provider capacity as well as request counts: [Groq rate limits](https://console.groq.com/docs/rate-limits) apply to tokens per minute and the provider account. No automatic retry loop is introduced.
