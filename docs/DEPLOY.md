# Deploying the daily agent

The agent is one FastAPI app plus a database. It runs fine on a laptop today. This file is what a host needs.

## Requirements
1. Python 3.12 and `uv`.
2. A database. SQLite file for a laptop, managed Postgres for a real host (`DATABASE_URL`).
3. HTTPS in front of it, and the host's secret store for every secret below. Never commit secrets.
4. A way to keep it running and to call `POST /sync/all` on a schedule (platform cron), or set `SYNC_INTERVAL_MINUTES` to sync inside the process.

## Steps
1. `uv sync`
2. Set the environment variables below.
3. `uv run alembic upgrade head` (run on every deploy).
4. `uv run uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000`
5. Check `GET /health`, then `GET /today` with `Authorization: Bearer <API_TOKEN>`.

## Environment variables
Names are the settings in `app/config.py`, upper case.

| Variable | Needed | Meaning |
|---|---|---|
| API_TOKEN | yes | long random bearer token, secret |
| DATABASE_URL | yes | SQLAlchemy URL |
| USER_TIMEZONE | no | IANA zone, default America/New_York |
| WORK_START | no | work day start, default 09:00 |
| WORK_END | no | work day end, default 17:00 |
| DEFAULT_EFFORT_MINUTES | no | effort for tasks with none, default 60 |
| LLM_MODEL | for AI text | model name, never hard coded |
| ANTHROPIC_API_KEY | for AI text | secret, without it explanations use a plain template |
| LLM_DAILY_TOKEN_BUDGET | no | daily token cap, default 20000 |
| STALE_OVERDUE_DAYS | no | overdue items older than this leave the ranking and show a warning, default 14, 0 keeps them |
| STALE_AFTER_HOURS | no | fallback stale threshold, default 26 |
| GOOGLE_CLIENT_SECRETS_PATH | for calendar | OAuth client JSON path, secret |
| GOOGLE_TOKEN_PATH | for calendar | saved token path, secret, re run `scripts/google_auth.py` weekly while the OAuth app is in Testing |
| CALENDAR_IDS | no | comma separated, default primary |
| ICOLLEGE_FEED_URL_PATH | for school | file holding the private feed URL, secret |
| OBSIDIAN_VAULT_PATH | for notes | local vault folder, hosted use needs a git checkout (separate spec) |
| OBSIDIAN_IGNORE_GLOBS | no | default templates/*,archive/* |
| ASK_PRIVATE_GLOBS | no | folders never indexed for ask |
| ASK_LLM_BLOCKED_GLOBS | no | searchable but never sent to the model, default cox/* |
| PLAID_CLIENT_ID | for money | Plaid client id |
| PLAID_SECRET | for money | Plaid secret for the chosen environment, secret |
| PLAID_ENV | no | sandbox (fake banks, default) or production |
| TOKEN_ENCRYPTION_KEY | for money | Fernet key that encrypts bank tokens at rest, secret, generate with `Fernet.generate_key()`, losing it means reconnecting banks |
| SYNC_INTERVAL_MINUTES | no | 0 turns the in process timer off |

## Host choice
Open (see `specs/09_sync_jobs.md`). Cloud Run plus Cloud Scheduler fits the budget. The Google token and iCollege feed file must exist on the host before calendar and school syncs work.
