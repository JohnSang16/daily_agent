# 09 Scheduled syncs and deployment

## Purpose
Keep data fresh automatically, safely, and cheaply, and put the backend online.

## Runner
1. `app/jobs/runner.py` exposes `run_sync(source)` and `run_all()`. Each calls the source's sync, wraps it in timing, writes a `sync_runs` row, and catches errors.
2. A lock per source prevents overlapping runs (database based lock or advisory lock). A second trigger while one is running returns "already running" and does nothing.
3. Protected endpoints `POST /sync/{source}` and `POST /sync/all` trigger runs. They require the bearer token.
4. Locally, an optional in process scheduler runs on a timer for development.
5. In production, the platform's cron (or a scheduled GitHub Actions workflow) calls the sync endpoints. This keeps the app stateless and scalable to zero.

## Schedule (defaults, configurable)
1. Google Calendar: every 15 minutes.
2. Obsidian: every 15 minutes.
3. Gmail digest: every 2 hours between 6 AM and 11 PM local time, and once more overnight.

## Staleness thresholds
1. Google Calendar and Obsidian: stale after 1 hour without a success.
2. Gmail digest: stale after 6 hours.
3. Staleness drives the `SOURCE_STALE` warning in spec 08.

## Failure handling
1. Retry with backoff inside a run for transient errors, with a cap.
2. After three consecutive failures for a source, record it prominently in the warnings. No automated alerts in v1.
3. Error summaries never include private text.

## Deployment
1. Choose a host (open question). Requirements: Python 3.12, environment variables for secrets, a managed Postgres, and HTTPS.
2. Run Alembic migrations on deploy.
3. Secrets live only in the host's secret store.
4. Add a `/health` check for the platform.
5. Document the exact steps in `docs/DEPLOY.md`.

## Acceptance criteria
* AC9.1 `run_sync` writes a `sync_runs` row with correct status, counts, and duration.
* AC9.2 A source exception is caught, recorded as `error`, and does not stop `run_all` from running the other sources.
* AC9.3 A second run started while the first holds the lock is skipped and reported as already running.
* AC9.4 `POST /sync/{source}` rejects unknown sources with 404 and requires the token.
* AC9.5 Staleness calculation returns the right warning at the thresholds (test with a fixed clock).
* AC9.6 A fake sleeper test shows retry and backoff stay within the cap.
* AC9.7 Error summaries in `sync_runs` contain no private text (assert on a fixture failure).
* AC9.8 `docs/DEPLOY.md` exists and lists every environment variable needed.
* AC9.9 After deployment, `/health` responds over HTTPS and `/today` works with the token (manual check by John).

## Out of scope
Alerting, dashboards, multi region.

## Open questions
1. Hosting choice and budget ceiling.
2. Cron mechanism: platform cron or GitHub Actions schedule.
