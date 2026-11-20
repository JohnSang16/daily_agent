import subprocess
import sys
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import inspect, select

from app.clock import FixedClock, get_clock
from app.config import Settings
from app.db import Base
from app.main import create_app
from app.models import Task
from app.schemas import TaskIn
from app.tasks_sync import sync_tasks

NY = "America/New_York"
NOW = datetime(2026, 11, 16, 14, 0, tzinfo=UTC)  # Mon 09:00 New York
H = {"Authorization": "Bearer tok"}


def build(tmp_path):
    s = Settings(_env_file=None, api_token="tok", database_url=f"sqlite:///{tmp_path}/t.db")
    app = create_app(s, sources={})
    Base.metadata.create_all(app.state.session_factory.kw["bind"])
    app.state.now = NOW
    app.dependency_overrides[get_clock] = lambda: FixedClock(app.state.now)
    return app, TestClient(app)


def today(c):
    return c.get("/today?date=2026-11-17", headers=H).json()


def titles(j):
    return [r["title"] for r in j["ranked"]]


def test_AC10a_1_manual_task_and_event_roundtrip(tmp_path):
    app, c = build(tmp_path)
    t = c.post("/items", headers=H, json={"kind": "task", "title": "Call mom", "due": "2026-11-17"})
    e = c.post(
        "/items",
        headers=H,
        json={
            "kind": "event",
            "title": "Dentist",
            "start": "2026-11-17T15:00:00Z",
            "end": "2026-11-17T16:00:00Z",
        },
    )
    assert t.status_code == 200 and e.status_code == 200
    j = today(c)
    assert "Call mom" in titles(j) and [x["title"] for x in j["events"]] == ["Dentist"]
    assert c.delete(f"/items/{t.json()['id']}", headers=H).status_code == 200
    assert c.delete(f"/items/{e.json()['id']}", headers=H).status_code == 200
    j = today(c)
    assert "Call mom" not in titles(j) and j["events"] == []


def test_patch_manual_task_and_event(tmp_path):
    app, c = build(tmp_path)
    t = c.post("/items", headers=H, json={"kind": "task", "title": "Call mom", "due": "2026-11-17"}).json()
    e = c.post(
        "/items",
        headers=H,
        json={
            "kind": "event",
            "title": "Dentist",
            "start": "2026-11-17T15:00:00Z",
            "end": "2026-11-17T16:00:00Z",
        },
    ).json()

    r = c.patch(f"/items/{t['id']}", headers=H, json={"title": "Call mom back", "due": "2026-11-18"})
    assert r.status_code == 200
    r = c.patch(
        f"/items/{e['id']}", headers=H,
        json={"title": "Dentist (moved)", "start": "2026-11-17T17:00:00Z", "end": "2026-11-17T18:00:00Z"},
    )
    assert r.status_code == 200

    j = c.get("/today?date=2026-11-18", headers=H).json()
    assert "Call mom back" in titles(j)
    j = c.get("/today?date=2026-11-17", headers=H).json()
    assert j["events"][0]["title"] == "Dentist (moved)"
    assert j["events"][0]["start"] == "2026-11-17T17:00:00Z"


def test_cannot_patch_other_sources(tmp_path):
    app, c = build(tmp_path)
    with app.state.session_factory() as db:
        sync_tasks(
            db, "obsidian", "a.md",
            [TaskIn(title="Essay", scope="a.md", source_ref="x", due_date=datetime(2026, 11, 20).date())],
            NOW, NY,
        )
        tid = db.scalars(select(Task.id)).first()
    assert c.patch(f"/items/task-{tid}", headers=H, json={"title": "hacked"}).status_code == 404


def test_AC10a_2_cannot_delete_other_sources(tmp_path):
    app, c = build(tmp_path)
    with app.state.session_factory() as db:
        sync_tasks(
            db,
            "obsidian",
            "a.md",
            [
                TaskIn(
                    title="Essay",
                    scope="a.md",
                    source_ref="x",
                    due_date=datetime(2026, 11, 20).date(),
                )
            ],
            NOW,
            NY,
        )
        tid = db.scalars(select(Task.id)).first()
    assert c.delete(f"/items/task-{tid}", headers=H).status_code == 404
    with app.state.session_factory() as db:
        assert db.scalars(select(Task)).first().status == "open"


def test_AC10a_3_goal(tmp_path):
    app, c = build(tmp_path)
    assert c.get("/goal/today", headers=H).json() == {"date": "2026-11-16", "text": None}
    assert c.put("/goal/today", headers=H, json={"text": "Ship spec 10a"}).status_code == 200
    assert c.get("/goal/today", headers=H).json()["text"] == "Ship spec 10a"
    assert c.put("/goal/today", headers=H, json={"text": "x" * 91}).status_code == 422
    assert c.put("/goal/today", headers=H, json={"text": "x" * 90}).status_code == 200
    app.state.now = NOW + timedelta(days=1)
    assert c.get("/goal/today", headers=H).json()["text"] is None


def test_AC10a_4_reminders_ingest(tmp_path):
    app, c = build(tmp_path)
    r = [
        {"id": "a", "title": "Buy milk", "due": "2026-11-20", "completed": False},
        {"id": "b", "title": "Pay rent", "due": "2026-11-21T09:00:00-05:00", "completed": False},
        {"id": "c", "title": "Old thing", "due": None, "completed": True},
    ]
    assert c.post("/ingest/reminders", headers=H, json={"reminders": r}).status_code == 200
    with app.state.session_factory() as db:
        rows = {t.title: t for t in db.scalars(select(Task))}
    assert all(t.source == "reminders" for t in rows.values()) and len(rows) == 3
    assert rows["Buy milk"].due_is_date_only and not rows["Pay rent"].due_is_date_only
    assert rows["Pay rent"].due_at == datetime(2026, 11, 21, 14, tzinfo=UTC)
    assert rows["Old thing"].status == "done"
    c.post("/ingest/reminders", headers=H, json={"reminders": r[:2]})
    with app.state.session_factory() as db:
        assert {t.title: t.status for t in db.scalars(select(Task))}["Old thing"] == "gone"


def _one_task(app):
    with app.state.session_factory() as db:
        sync_tasks(
            db,
            "obsidian",
            "a.md",
            [
                TaskIn(
                    title="Essay",
                    scope="a.md",
                    source_ref="x",
                    due_date=datetime(2026, 11, 20).date(),
                )
            ],
            NOW,
            NY,
        )
        return db.scalars(select(Task.id)).first()


def test_AC10a_5_snooze(tmp_path):
    app, c = build(tmp_path)
    tid = _one_task(app)
    until = (NOW + timedelta(hours=2)).isoformat()
    assert c.post(f"/tasks/{tid}/snooze", headers=H, json={"until": until}).status_code == 200
    assert "Essay" not in titles(today(c))
    app.state.now = NOW + timedelta(hours=3)
    assert "Essay" in titles(today(c))
    past = (NOW - timedelta(hours=1)).isoformat()
    assert c.post(f"/tasks/{tid}/snooze", headers=H, json={"until": past}).status_code == 422


def test_AC10a_6_done_survives_sync(tmp_path):
    app, c = build(tmp_path)
    tid = _one_task(app)
    assert c.post(f"/tasks/{tid}/done", headers=H).status_code == 200
    assert "Essay" not in titles(today(c))
    with app.state.session_factory() as db:
        sync_tasks(
            db,
            "obsidian",
            "a.md",
            [
                TaskIn(
                    title="Essay",
                    scope="a.md",
                    source_ref="x",
                    due_date=datetime(2026, 11, 20).date(),
                )
            ],
            NOW,
            NY,
        )
        assert db.get(Task, tid).status == "done"
    assert c.post("/tasks/9999/done", headers=H).status_code == 404


def test_AC10a_7_auth_required(tmp_path):
    app, c = build(tmp_path)
    for method, url, body in [
        ("post", "/items", {"kind": "task", "title": "x"}),
        ("delete", "/items/task-1", None),
        ("get", "/goal/today", None),
        ("put", "/goal/today", {"text": "x"}),
        ("post", "/ingest/reminders", {"reminders": []}),
        ("post", "/tasks/1/snooze", {"until": NOW.isoformat()}),
        ("post", "/tasks/1/done", None),
    ]:
        assert c.request(method.upper(), url, json=body).status_code == 401, url


def test_AC10a_8_migration(tmp_path):
    env = {"DATABASE_URL": f"sqlite:///{tmp_path}/m.db", "API_TOKEN": "t", "PATH": "/usr/bin:/bin"}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
        env=env,
        capture_output=True,
    )
    from sqlalchemy import create_engine

    insp = inspect(create_engine(env["DATABASE_URL"]))
    assert "daily_goal" in insp.get_table_names()
    assert "locally_done" in {c["name"] for c in insp.get_columns("tasks")}
