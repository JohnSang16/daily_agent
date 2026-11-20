"""Spec 18: check-in, input and outcome goals, never miss twice, say/do, done_today."""

from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.clock import FixedClock, get_clock
from app.config import Settings
from app.db import Base
from app.main import create_app
from app.models import DailyCheckin, Goal, GoalLog
from app.schemas import TaskIn
from app.tasks_sync import sync_tasks

NY = "America/New_York"
NOW = datetime(2026, 11, 19, 15, 0, tzinfo=UTC)  # Thu 10:00 New York
TODAY = date(2026, 11, 19)
H = {"Authorization": "Bearer tok"}


@pytest.fixture
def app(tmp_path):
    st = Settings(_env_file=None, api_token="tok", database_url=f"sqlite:///{tmp_path}/t.db")
    a = create_app(st, sources={})
    Base.metadata.create_all(a.state.session_factory.kw["bind"])
    a.dependency_overrides[get_clock] = lambda: FixedClock(NOW)
    return a


@pytest.fixture
def c(app):
    return TestClient(app)


def day(n: int) -> str:
    return (TODAY - timedelta(days=n)).isoformat()


def test_AC18_1_partial_checkin_keeps_other_fields(c):
    c.put("/checkin/today", headers=H, json={"if_then": "phone in the other room"})
    c.put("/checkin/today", headers=H, json={"obstacle": "scrolling"})
    j = c.get("/checkin/today", headers=H).json()
    assert (
        j["today"]["obstacle"] == "scrolling" and j["today"]["if_then"] == "phone in the other room"
    )
    assert j["today"]["did_top"] is None


def test_AC18_2_long_checkin_rejected(c):
    assert c.put("/checkin/today", headers=H, json={"why_not": "x" * 201}).status_code == 422


def test_AC18_3_and_4_say_do_and_yesterday(app, c):
    with app.state.session_factory() as db:
        for n, kept in [(1, False), (2, True), (3, True), (5, True)]:
            db.add(
                DailyCheckin(
                    day=day(n),
                    did_top=kept,
                    top_task_title="OA",
                    why_not=None if kept else "slept in",
                    updated_at=NOW,
                )
            )
        db.add(DailyCheckin(day=day(4), obstacle="no answer that day", updated_at=NOW))
        db.add(DailyCheckin(day=day(20), did_top=False, updated_at=NOW))  # outside 14 days
        db.commit()
    c.put("/checkin/today", headers=H, json={"did_top": True})  # today never counts
    j = c.get("/checkin/today", headers=H).json()
    assert j["say_do"] == {"kept": 3, "of": 4}
    assert j["yesterday"] == {"top_task_title": "OA", "did_top": False, "why_not": "slept in"}


def make(c, **kw):
    body = {"name": "leetcode problems", "kind": "input", "unit": "problems", "target": 1, **kw}
    r = c.post("/goals", headers=H, json=body)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def goal(c, gid):
    return next(g for g in c.get("/goals", headers=H).json() if g["id"] == gid)


def test_AC18_5_input_goal_today(c):
    gid = make(c)
    assert c.put(f"/goals/{gid}/today", headers=H, json={"count": 2}).status_code == 200
    g = goal(c, gid)
    assert g["today"] == 2 and g["last7"][-1] == 2 and len(g["last7"]) == 7 and g["hit7"] == 1
    assert g["total30"] == 2


def _backdate(app, gid, created_days_ago, counts):
    with app.state.session_factory() as db:
        g = db.get(Goal, gid)
        g.created_at = NOW - timedelta(days=created_days_ago)
        for n, cnt in counts.items():
            db.merge(GoalLog(goal_id=gid, day=day(n), count=cnt))
        db.commit()


def test_AC18_6_missed_twice(app, c):
    two = make(c, name="two misses")
    _backdate(app, two, 10, {3: 1})
    one = make(c, name="one miss")
    _backdate(app, one, 10, {2: 1})
    fresh = make(c, name="new yesterday")
    _backdate(app, fresh, 1, {})
    assert goal(c, two)["missed_twice"] is True
    assert goal(c, one)["missed_twice"] is False
    assert goal(c, fresh)["missed_twice"] is False


def test_AC18_7_outcome_goal(c):
    gid = make(c, name="Roth IRA", kind="outcome", unit="dollars", target=7500, current=1450)
    g = goal(c, gid)
    assert g["kind"] == "outcome" and g["current"] == 1450 and g["target"] == 7500
    c.patch(f"/goals/{gid}", headers=H, json={"current": 2000})
    assert goal(c, gid)["current"] == 2000


def test_AC18_8_delete_archives(app, c):
    gid = make(c)
    c.put(f"/goals/{gid}/today", headers=H, json={"count": 1})
    assert c.delete(f"/goals/{gid}", headers=H).status_code == 200
    assert all(g["id"] != gid for g in c.get("/goals", headers=H).json())
    with app.state.session_factory() as db:
        assert db.get(GoalLog, (gid, TODAY.isoformat())) is not None


@pytest.mark.parametrize(
    "body",
    [
        {"name": "x", "kind": "habit", "unit": "u", "target": 1},
        {"name": "x", "kind": "input", "unit": "u", "target": 0},
        {"name": "x" * 61, "kind": "input", "unit": "u", "target": 1},
    ],
)
def test_AC18_9_bad_goals_rejected(c, body):
    assert c.post("/goals", headers=H, json=body).status_code == 422


def test_AC18_9_negative_count_rejected(c):
    gid = make(c)
    assert c.put(f"/goals/{gid}/today", headers=H, json={"count": -1}).status_code == 422
    assert c.put("/goals/999/today", headers=H, json={"count": 1}).status_code == 404


def test_AC18_10_done_today(app, c):
    items = [
        TaskIn(title=t, scope="a.md", source_ref=f"a.md:{i}", due_date=date(2026, 11, 25))
        for i, t in enumerate(["A", "B", "C"])
    ]
    with app.state.session_factory() as db:
        sync_tasks(db, "obsidian", "a.md", items, NOW, NY)
    ids = [t["id"] for t in c.get("/today", headers=H).json()["ranked"]]
    c.post(f"/tasks/{ids[0]}/done", headers=H)
    c.post(f"/tasks/{ids[1]}/done", headers=H)
    yesterday = FixedClock(NOW - timedelta(days=1))
    app.dependency_overrides[get_clock] = lambda: yesterday
    c.post(f"/tasks/{ids[2]}/done", headers=H)
    app.dependency_overrides[get_clock] = lambda: FixedClock(NOW)
    assert c.get("/today", headers=H).json()["done_today"] == 2


@pytest.mark.parametrize(
    "method,url",
    [
        ("get", "/checkin/today"),
        ("put", "/checkin/today"),
        ("get", "/goals"),
        ("post", "/goals"),
        ("patch", "/goals/1"),
        ("delete", "/goals/1"),
        ("put", "/goals/1/today"),
    ],
)
def test_AC18_11_auth(c, method, url):
    assert getattr(c, method)(url).status_code == 401
