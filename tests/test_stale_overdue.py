from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.clock import FixedClock, get_clock
from app.config import Settings
from app.db import Base
from app.llm.explain import format_due, template_text
from app.main import create_app
from app.models import Task
from app.priority.engine import Config, TaskView, rank
from app.schemas import TaskIn
from app.tasks_sync import sync_tasks

NY = "America/New_York"
NOW = datetime(2026, 11, 19, 21, 0, tzinfo=UTC)  # Thu 16:00 New York
H = {"Authorization": "Bearer tok"}


def tv(id, due):
    return TaskView(id, due, 30, 3, NOW - timedelta(days=60))


def test_old_overdue_drops_out_and_is_reported():
    old = tv(1, NOW - timedelta(days=180))
    recent = tv(2, NOW - timedelta(days=3))
    soon = tv(3, NOW + timedelta(days=2))
    r = rank([old, recent, soon], [], NOW, Config())
    assert [i.task_id for i in r.ranked] == [2, 3]  # 3 day overdue still ranks first
    assert r.stale_ids == [1]


def test_cutoff_can_be_turned_off():
    old = tv(1, NOW - timedelta(days=180))
    r = rank([old], [], NOW, Config(stale_overdue_days=0))
    assert [i.task_id for i in r.ranked] == [1] and r.stale_ids == []


def test_boundary_exactly_at_the_cutoff_stays():
    edge = tv(1, NOW - timedelta(days=14))
    assert [i.task_id for i in rank([edge], [], NOW, Config()).ranked] == [1]
    over = tv(2, NOW - timedelta(days=14, seconds=1))
    assert rank([over], [], NOW, Config()).stale_ids == [2]


def _app(tmp_path, **kw):
    s = Settings(_env_file=None, api_token="tok", database_url=f"sqlite:///{tmp_path}/t.db", **kw)
    app = create_app(s, sources={})
    Base.metadata.create_all(app.state.session_factory.kw["bind"])
    app.dependency_overrides[get_clock] = lambda: FixedClock(NOW)
    return app


def test_today_hides_old_overdue_and_warns(tmp_path):
    app = _app(tmp_path)
    with app.state.session_factory() as db:
        sync_tasks(
            db,
            "reminders",
            "reminders",
            [
                TaskIn(
                    title="LEETCODE", scope="reminders", source_ref="a", due_date=date(2026, 5, 24)
                ),
                TaskIn(
                    title="Withdrawal",
                    scope="reminders",
                    source_ref="b",
                    due_date=date(2026, 5, 27),
                ),
                TaskIn(
                    title="Essay", scope="reminders", source_ref="c", due_date=date(2026, 11, 25)
                ),
            ],
            NOW,
            NY,
        )
    j = TestClient(app).get("/today", headers=H).json()
    assert [r["title"] for r in j["ranked"]] == ["Essay"]
    w = [x for x in j["warnings"] if x["code"] == "STALE_OVERDUE"]
    assert len(w) == 1 and "2" in w[0]["detail"]
    assert "LEETCODE" not in j["explanation"]["text"]
    with app.state.session_factory() as db:  # hidden, not deleted
        assert len(db.scalars(select(Task)).all()) == 3


def test_setting_zero_keeps_old_items(tmp_path):
    app = _app(tmp_path, stale_overdue_days=0)
    with app.state.session_factory() as db:
        sync_tasks(
            db,
            "reminders",
            "reminders",
            [
                TaskIn(
                    title="LEETCODE", scope="reminders", source_ref="a", due_date=date(2026, 5, 24)
                )
            ],
            NOW,
            NY,
        )
    j = TestClient(app).get("/today", headers=H).json()
    assert [r["title"] for r in j["ranked"]] == ["LEETCODE"]
    assert not [x for x in j["warnings"] if x["code"] == "STALE_OVERDUE"]


def test_due_dates_are_written_for_people_not_computers():
    assert format_due("2026-05-25T03:59:59Z", NY) == "Sun May 24"  # date only, end of that day
    assert format_due("2026-12-02T22:17:00Z", NY) == "Wed Dec 2 at 5:17 PM"
    assert format_due("2026-12-02T14:05:00Z", NY) == "Wed Dec 2 at 9:05 AM"
    assert format_due(None, NY) is None


def test_template_text_has_no_raw_timestamp(tmp_path):
    app = _app(tmp_path)
    with app.state.session_factory() as db:
        sync_tasks(
            db,
            "obsidian",
            "a.md",
            [TaskIn(title="Essay", scope="a.md", source_ref="x", due_date=date(2026, 11, 25))],
            NOW,
            NY,
        )
    text = TestClient(app).get("/today", headers=H).json()["explanation"]["text"]
    assert "Essay" in text and "T04:59" not in text and "Z." not in text and "Wed Nov 25" in text
    plain = template_text(
        {
            "ranking": [
                {"title": "X", "due_at": "2026-12-02T22:17:00Z", "reasons": [], "at_risk": False}
            ]
        }
    )
    assert "X" in plain  # still works for payloads that only have the raw timestamp
