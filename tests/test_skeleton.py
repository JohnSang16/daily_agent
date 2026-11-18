import logging
import subprocess
import sys
from datetime import UTC, datetime

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.clock import Clock, FixedClock, get_clock
from app.config import Settings
from app.logging_config import RedactionFilter
from app.main import create_app

TOKEN = "test-token-123"


def make_settings(**kw):
    base = {"api_token": TOKEN, "database_url": "sqlite://"}
    return Settings(_env_file=None, **{**base, **kw})


def test_AC2_1_health_open():
    r = TestClient(create_app(make_settings())).get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["version"]


def _app_with_protected():
    from app.auth import require_token

    app = create_app(make_settings())

    @app.get("/p", dependencies=[Depends(require_token)])
    def p():
        return {"ok": True}

    return TestClient(app)


def test_AC2_2_auth_401_and_200():
    c = _app_with_protected()
    assert c.get("/p").status_code == 401
    assert c.get("/p", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert c.get("/p", headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 200
    # response never reveals which part was wrong
    assert c.get("/p").json() == c.get("/p", headers={"Authorization": "Bearer wrong"}).json()


def test_AC2_3_constant_time_compare(monkeypatch):
    import app.auth as auth

    calls = []
    real = auth.hmac.compare_digest
    monkeypatch.setattr(auth.hmac, "compare_digest", lambda a, b: calls.append(1) or real(a, b))
    _app_with_protected().get("/p", headers={"Authorization": f"Bearer {TOKEN}"})
    assert calls


def test_AC2_4_missing_token_names_variable_no_values(monkeypatch):
    monkeypatch.delenv("API_TOKEN", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite://secret-db-value")
    with pytest.raises(ValidationError) as e:
        Settings(_env_file=None)
    msg = str(e.value)
    assert "api_token" in msg.lower()
    assert "secret-db-value" not in msg


def test_AC2_5_invalid_timezone():
    with pytest.raises(ValidationError):
        make_settings(user_timezone="Not/AZone")
    assert make_settings().user_timezone == "America/New_York"


def test_AC2_6_fixed_clock_injected():
    app = create_app(make_settings())
    frozen = datetime(2026, 1, 2, 3, 4, tzinfo=UTC)
    app.dependency_overrides[get_clock] = lambda: FixedClock(frozen)

    @app.get("/now")
    def now(clock: Clock = Depends(get_clock)):
        return {"now": clock.now().isoformat()}

    assert TestClient(app).get("/now").json() == {"now": frozen.isoformat()}


def test_AC2_7_redaction_filter_removes_bearer_and_secret_values():
    f = RedactionFilter(secrets=["hunter2-secret"])
    rec = logging.LogRecord(
        "t", logging.INFO, "", 0, "auth Bearer abc.DEF-123 and hunter2-secret", None, None
    )
    f.filter(rec)
    out = rec.getMessage()
    assert "abc.DEF-123" not in out and "hunter2-secret" not in out


def test_AC2_9_alembic_upgrade_head(tmp_path):
    env = {
        "DATABASE_URL": f"sqlite:///{tmp_path}/t.db",
        "API_TOKEN": TOKEN,
        "PATH": "/usr/bin:/bin",
    }
    r = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert r.returncode == 0, r.stderr
