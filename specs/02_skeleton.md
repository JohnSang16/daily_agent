# 02 Project skeleton

## Purpose
A running, tested FastAPI app with config, auth, database, logging, and tooling, so every later spec plugs into a stable base.

## Scope
1. Project setup with `uv`, `pyproject.toml`, ruff, pytest.
2. `app/main.py` with an app factory function `create_app(settings)`.
3. `app/config.py`: typed settings loaded from environment and `.env`, with validation. Missing required settings fail fast at startup with a clear message that names the variable but never prints values.
4. `app/auth.py`: a dependency that requires `Authorization: Bearer <API_TOKEN>` and compares in constant time.
5. `app/api/health.py`: `GET /health` with no auth.
6. `app/clock.py`: a `Clock` interface with a system implementation and a fixed implementation for tests.
7. `app/db.py` and Alembic set up, with an empty initial migration that runs on SQLite.
8. Logging: structured logs, request id per request, a redaction filter that removes bearer tokens and anything matching configured secret values.
9. Pre commit hooks: ruff and a secret scanner.
10. A GitHub Actions workflow that runs lint and tests on push (optional, ask me before adding).

## Requirements
1. `GET /health` returns `{"status": "ok", "version": "<package version>"}` with HTTP 200 and needs no token.
2. Every other route returns HTTP 401 with a JSON body when the token is missing or wrong, and the response never reveals which part was wrong.
3. The app starts with only `API_TOKEN` and `DATABASE_URL` set. Other settings are optional until their spec needs them.
4. Settings expose a `user_timezone` that is validated as a real IANA time zone name.
5. The clock is injected through FastAPI dependencies so tests can freeze time.
6. No route reads `os.environ` directly. Everything goes through settings.

## Acceptance criteria
* AC2.1 `GET /health` returns 200 and the expected JSON without a token.
* AC2.2 A protected test route returns 401 with no token, 401 with a wrong token, and 200 with the right token.
* AC2.3 The token comparison uses a constant time function (assert in a unit test by checking the function used, or by wrapper).
* AC2.4 Starting the app with `API_TOKEN` missing raises a clear error that names the missing variable and does not print any secret values.
* AC2.5 An invalid `USER_TIMEZONE` fails settings validation.
* AC2.6 A fixed clock can be injected and a route can read the frozen time.
* AC2.7 The log redaction filter removes a bearer token from a log message in a test.
* AC2.8 `uv run pytest` and `uv run ruff check .` pass on a clean checkout.
* AC2.9 Alembic upgrade to head succeeds on a fresh SQLite database.

## Out of scope
Any real source, any LLM call, any user facing feature.

## Open questions
1. Add the optional GitHub Actions workflow now or later?
2. Which secret scanner for pre commit (gitleaks is the default suggestion)?
