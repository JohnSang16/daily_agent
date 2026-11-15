# Plan: spec 02 skeleton

Tasks (each tied to acceptance criteria):
1. pyproject + uv + ruff + pytest config (AC2.8)
2. tests first for AC2.1 to AC2.9, confirm they fail
3. config.py, clock.py, auth.py, api/health.py, main.py (AC2.1 to AC2.6)
4. logging with redaction filter + request id (AC2.7)
5. db.py + Alembic empty initial migration (AC2.9)
6. pre-commit: ruff + gitleaks (scope item 9). No GitHub Actions (John decided, solo project).

New dependencies (one-line reasons):
- fastapi, uvicorn: the API server (settled in principles)
- pydantic-settings: typed env settings with validation (settled: Pydantic v2 settings)
- sqlalchemy, alembic: DB layer and migrations (settled)
- dev: pytest (tests), httpx (FastAPI TestClient needs it), ruff (lint), pre-commit (runs ruff + gitleaks hooks)
