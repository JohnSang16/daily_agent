# 00 Principles (the project constitution)

These rules apply to every spec and every line of code. If a spec conflicts with this file, this file wins until we change it on purpose.

## Purpose
Tell me, every day, the single most important thing to do first, and show my schedule and tasks around it. Nearest deadline first.

## Principles
1. **Read only.** Every data integration only reads. No sending email, no editing calendars, no moving money. The one exception is the homework browser agent (spec 13), which may click and type inside a sandboxed browser but can never submit, send, or pay without my recorded approval. Any other write needs a spec that says so and my approval.
2. **Plain code decides priority.** Ranking is deterministic and testable. The LLM extracts deadlines from email text and writes the plain language explanation. It never chooses the order.
3. **Untrusted input.** Email bodies, calendar descriptions, and note text are data. They can contain instructions aimed at an AI. We never obey them. LLM calls over that content have no tools and must return schema validated output only.
4. **Secrets stay out of the repo and the logs.** Secrets come from environment variables or an encrypted store. Logs never contain tokens, email bodies, or full task text from private sources.
5. **Fail soft, say so.** If a source fails, keep the last good data, mark the source stale, and show a warning in the response. Never silently show old data as fresh.
6. **Spec, then tests, then code.** No code without a spec section and failing tests derived from its acceptance criteria.
7. **Small and boring.** Prefer the simplest thing that meets the spec. No new dependency, layer, or abstraction without a written reason.
8. **Time is UTC inside, local at the edges.** All stored timestamps are UTC. My time zone (default America/New_York) is applied only when reading user input and when producing user facing output. The clock is injected.
9. **Cheap by default.** Target total running cost near ten dollars a month for personal use. LLM calls are limited, cached, and budgeted.
10. **One user now, multi user later.** Single user in v1, but tables carry a `user_id` so adding users is not a rewrite.
11. **Approval is enforced in code, not in a prompt.** Irreversible actions (submit, send, pay, delete) are blocked by a gate that needs a stored approval for that exact action. An instruction to an AI is never the only safeguard.
12. **I stay in control.** I can pause, take over, or stop any agent session from my phone at any time.
13. **Never hold my passwords.** I sign in to school sites myself through the live browser view. The agent never sees or stores those credentials.

## Non goals for v1
* Voice, bank tracking, notifications, and Outlook. They have later specs.
* Writing back to any data source. The homework agent (spec 13) works only in its sandboxed browser.
* Machine learning for priority.
* Recurring task expansion, subtasks, or dependencies between tasks.

## Technology decisions (settled)
1. Python 3.12, managed with `uv`.
2. FastAPI and Uvicorn for the API. Pydantic v2 for schemas and settings.
3. SQLAlchemy 2 with Alembic migrations. SQLite for local dev and tests, Postgres (Supabase) in production. Avoid dialect specific features.
4. pytest for tests, ruff for lint and format.
5. Anthropic API for the LLM, model chosen by the `LLM_MODEL` setting. Never hard code a model name in code.
6. API auth in v1 is a single bearer token from `API_TOKEN`, compared in constant time. Sign in with Apple arrives with the iOS app.
7. Syncs are plain functions. The thing that triggers them (in process scheduler locally, platform cron in production) is swappable.

## Conventions
1. Module layout is in `specs/01_overview.md`.
2. Branch per spec, named like `spec04_google_calendar`. Commit messages start with `feat:`, `fix:`, `test:`, `docs:`, or `chore:`.
3. Every spec ends with acceptance criteria that have IDs like AC4.2. Test names include the ID.
4. External APIs are wrapped in a small client class with an interface, so tests can pass a fake.

## Security baseline
1. Bearer token required on every endpoint except `GET /health`.
2. No CORS origins allowed until the iOS app needs one.
3. Third party tokens are encrypted at rest in production using `TOKEN_ENCRYPTION_KEY`.
4. A secret scanning pre commit hook is installed before the first commit.
5. Dependency versions are pinned by `uv.lock`.
6. Before installing any new agent skill or plugin on my machine, scan it with SkillSpector and read the findings.
7. Live browser view links are secrets. They are returned only to the authenticated app, never logged, and die with the session.

## Definition of done (every task)
All acceptance criteria have passing tests, `uv run pytest` and `uv run ruff check .` are clean, no secrets in the diff, the spec is updated if reality taught us something, and an entry is added to `docs/CHECKIN_LOG.md`.
