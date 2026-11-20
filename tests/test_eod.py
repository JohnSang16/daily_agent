"""The nightly EOD bullets: answered flag, tasks_done_today and goal snapshot, vault write."""

from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient

from app.clock import FixedClock, get_clock
from app.config import Settings
from app.db import Base
from app.main import create_app
from app.models import DailyGoal, Task

NY = "America/New_York"
NOW = datetime(2026, 11, 20, 15, 0, tzinfo=UTC)  # Fri 10:00 New York
TODAY = date(2026, 11, 20)
H = {"Authorization": "Bearer tok"}


@pytest.fixture
def app(tmp_path):
    st = Settings(
        _env_file=None,
        api_token="tok",
        database_url=f"sqlite:///{tmp_path}/t.db",
        obsidian_vault_path=str(tmp_path / "vault"),
    )
    a = create_app(st, sources={})
    Base.metadata.create_all(a.state.session_factory.kw["bind"])
    a.dependency_overrides[get_clock] = lambda: FixedClock(NOW)
    return a


@pytest.fixture
def c(app):
    return TestClient(app)


def test_not_answered_before_a_put(c):
    r = c.get("/eod/today", headers=H)
    assert r.status_code == 200
    assert r.json()["answered"] is False
    assert r.json()["bullets"] is None


def test_put_marks_answered_and_echoes_bullets(c):
    r = c.put("/eod/today", json={"bullets": "- shipped x\n- fixed y"}, headers=H)
    assert r.status_code == 200
    assert r.json() == {"date": "2026-11-20", "answered": True, "bullets": "- shipped x\n- fixed y"}
    assert c.get("/eod/today", headers=H).json()["answered"] is True


def test_put_snapshots_tasks_done_and_goal_into_the_vault_file(c, app, tmp_path):
    with app.state.session_factory() as db:
        db.add(DailyGoal(day="2026-11-20", text="ship the eod log", updated_at=NOW))
        db.add(
            Task(
                title="t1", scope="s", source="obsidian", source_ref="s:1", fingerprint="fp1",
                status="done", locally_done=True, created_at=NOW, updated_at=NOW,
                last_seen_at=NOW, user_id=1,
            )
        )
        db.commit()

    r = c.put("/eod/today", json={"bullets": "- did the thing"}, headers=H)
    assert r.json()["bullets"] == "- did the thing"

    written = (tmp_path / "vault" / "daily-agent-logs" / "2026-11-20.md").read_text()
    assert "tasks done: 1" in written
    assert "goal: ship the eod log" in written
    assert "- did the thing" in written


def test_goal_is_none_when_nothing_logged_today(c):
    r = c.get("/eod/today", headers=H)
    assert r.json()["goal"] is None


def test_blank_bullets_rejected(c):
    r = c.put("/eod/today", json={"bullets": "   "}, headers=H)
    assert r.status_code == 422
    assert c.get("/eod/today", headers=H).json()["answered"] is False
