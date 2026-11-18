import threading
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.clock import FixedClock, get_clock
from app.config import Settings
from app.db import Base
from app.jobs.runner import default_sources, scheduler_loop, stale_hours_for
from app.main import create_app
from app.models import SyncRun

NOW = datetime(2026, 11, 16, 14, 0, tzinfo=UTC)
H = {"Authorization": "Bearer tok"}


def build(sources):
    s = Settings(_env_file=None, api_token="tok", database_url="sqlite://")
    app = create_app(s, sources=sources)
    Base.metadata.create_all(app.state.session_factory.kw["bind"])
    app.dependency_overrides[get_clock] = lambda: FixedClock(NOW)
    return app


def runs(app):
    with app.state.session_factory() as db:
        return list(db.scalars(select(SyncRun).order_by(SyncRun.id)))


def test_AC9_1_run_sync_writes_row():
    app = build({"fake": lambda s, now: 3})
    assert app.state.runner.run_sync("fake")["status"] == "ok"
    (r,) = runs(app)
    assert (r.source, r.status, r.items_changed) == ("fake", "ok", 3)
    assert r.duration_ms is not None and r.finished_at is not None


def test_AC9_2_failure_does_not_stop_run_all():
    def boom(s, now):
        raise RuntimeError("x")

    app = build({"a": boom, "b": lambda s, now: 1})
    res = app.state.runner.run_all()
    assert res["a"]["status"] == "error" and res["b"]["status"] == "ok"
    assert {r.source: r.status for r in runs(app)} == {"a": "error", "b": "ok"}


def test_AC9_3_overlapping_run_skipped():
    started, release = threading.Event(), threading.Event()

    def slow(s, now):
        started.set()
        release.wait(5)
        return 0

    app = build({"slow": slow})
    t = threading.Thread(target=app.state.runner.run_sync, args=("slow",))
    t.start()
    assert started.wait(5)
    assert app.state.runner.run_sync("slow")["status"] == "already_running"
    release.set()
    t.join()
    assert [r.status for r in runs(app)] == ["ok"]


def test_AC9_4_endpoints():
    app = build({"fake": lambda s, now: 2})
    c = TestClient(app)
    assert c.post("/sync/fake").status_code == 401
    assert c.post("/sync/nope", headers=H).status_code == 404
    assert c.post("/sync/fake", headers=H).json()["status"] == "ok"
    assert c.post("/sync/all", headers=H).json()["fake"]["status"] == "ok"


def test_AC9_5_staleness_thresholds():
    assert stale_hours_for("google_calendar", 26) == 1
    assert stale_hours_for("obsidian", 26) == 1
    assert stale_hours_for("gmail_digest", 26) == 6
    assert stale_hours_for("icollege", 26) == 6
    assert stale_hours_for("something_else", 26) == 26


@pytest.mark.parametrize(
    "source,age_h,stale",
    [
        ("google_calendar", 0.9, False),
        ("google_calendar", 1.1, True),
        ("gmail_digest", 5, False),
        ("gmail_digest", 7, True),
    ],
)
def test_AC9_5_today_warns_at_threshold(source, age_h, stale):
    app = build({})
    t = NOW - timedelta(hours=age_h)
    with app.state.session_factory() as db:
        db.add(SyncRun(source=source, started_at=t, finished_at=t, status="ok"))
        db.commit()
    w = TestClient(app).get("/today", headers=H).json()["warnings"]
    assert any(x["code"] == "SOURCE_STALE" for x in w) is stale


def test_AC9_7_error_summary_has_no_private_text():
    def boom(s, now):
        raise RuntimeError("PRIVATE-TASK-TITLE")

    app = build({"a": boom})
    app.state.runner.run_sync("a")
    assert all("PRIVATE-TASK-TITLE" not in (r.error_summary or "") for r in runs(app))


def test_scheduler_loop_runs_repeatedly_until_stopped():
    stop, calls = threading.Event(), []

    def run():
        calls.append(1)
        if len(calls) == 3:
            stop.set()

    scheduler_loop(run, 0.001, stop)
    assert len(calls) == 3


def test_default_sources_include_icollege():
    s = Settings(_env_file=None, api_token="tok", database_url="sqlite://")
    assert set(default_sources(s, http=None)) == {"google_calendar", "obsidian", "icollege"}
