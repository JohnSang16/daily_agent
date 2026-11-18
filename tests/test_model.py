from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError
from sqlalchemy import inspect, select

from app.db import Base, make_session_factory
from app.models import Task
from app.schemas import EventIn, TaskIn
from app.tasks_sync import all_day_bounds, date_only_due_to_utc, sync_tasks

NY = "America/New_York"
T0 = datetime(2026, 11, 1, 12, tzinfo=UTC)


@pytest.fixture
def session():
    sf = make_session_factory("sqlite://")
    Base.metadata.create_all(sf.kw["bind"])
    with sf() as s:
        yield s


def ti(title, scope="a.md", **kw):
    return TaskIn(title=title, scope=scope, source_ref=scope, **kw)


def run(s, items, now=T0, success=True, scope="a.md"):
    return sync_tasks(s, "obsidian", scope, items, now, NY, success=success)


def all_tasks(s):
    return list(s.scalars(select(Task).order_by(Task.id)))


def test_AC3_1_tables_created(session):
    names = set(inspect(session.get_bind()).get_table_names())
    assert {
        "tasks",
        "events",
        "sync_runs",
        "oauth_tokens",
        "llm_usage",
        "explanation_cache",
    } <= names


def test_AC3_1_alembic_creates_all_tables(tmp_path):
    import subprocess
    import sys

    from sqlalchemy import create_engine

    url = f"sqlite:///{tmp_path}/m.db"
    env = {"DATABASE_URL": url, "API_TOKEN": "x", "PATH": "/usr/bin:/bin"}
    r = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert r.returncode == 0, r.stderr
    names = set(inspect(create_engine(url)).get_table_names())
    assert {
        "tasks",
        "events",
        "sync_runs",
        "oauth_tokens",
        "llm_usage",
        "explanation_cache",
    } <= names


def test_AC3_2_upsert_twice_one_row(session):
    run(session, [ti("Write essay")])
    run(session, [ti("Write essay")])
    assert len(all_tasks(session)) == 1


def test_AC3_3_missing_becomes_gone_only_on_success(session):
    run(session, [ti("A"), ti("B")])
    run(session, [ti("A")], success=False)
    assert {t.status for t in all_tasks(session)} == {"open"}
    run(session, [ti("A")])
    st = {t.title: t.status for t in all_tasks(session)}
    assert st == {"A": "open", "B": "gone"}


def test_AC3_3_other_scope_untouched(session):
    run(session, [ti("A", "a.md")], scope="a.md")
    run(session, [ti("Z", "b.md")], scope="b.md")
    assert {t.status for t in all_tasks(session)} == {"open"}


def test_AC3_4_gone_reappears_open(session):
    run(session, [ti("A")])
    run(session, [])
    assert all_tasks(session)[0].status == "gone"
    run(session, [ti("A")])
    assert all_tasks(session)[0].status == "open"


def test_done_in_source_becomes_done(session):
    run(session, [ti("A")])
    run(session, [ti("A", done=True)])
    assert all_tasks(session)[0].status == "done"


def test_AC3_5_snooze_survives_title_case_change(session):
    run(session, [ti("write essay")])
    t = all_tasks(session)[0]
    t.snoozed_until = T0 + timedelta(days=2)
    session.commit()
    run(session, [ti("Write Essay")])
    rows = all_tasks(session)
    assert len(rows) == 1 and rows[0].title == "Write Essay"
    assert rows[0].snoozed_until == T0 + timedelta(days=2)


def test_AC3_9_duplicate_titles_get_distinct_fingerprints(session):
    run(session, [ti("Call mom"), ti("Call mom")])
    rows = all_tasks(session)
    assert len(rows) == 2 and rows[0].fingerprint != rows[1].fingerprint
    run(session, [ti("Call mom"), ti("Call mom")])
    assert len(all_tasks(session)) == 2


def test_AC3_6_date_only_due_end_of_local_day_incl_dst():
    # normal day, EST (UTC-5)
    assert date_only_due_to_utc(date(2026, 12, 1), NY) == datetime(
        2026, 12, 2, 4, 59, 59, tzinfo=UTC
    )
    # spring forward day (Mar 8 2026), end of day is EDT (UTC-4)
    assert date_only_due_to_utc(date(2026, 3, 8), NY) == datetime(2026, 3, 9, 3, 59, 59, tzinfo=UTC)
    # fall back day (Nov 1 2026), end of day is EST (UTC-5)
    assert date_only_due_to_utc(date(2026, 11, 1), NY) == datetime(
        2026, 11, 2, 4, 59, 59, tzinfo=UTC
    )


def test_AC3_6_stored_in_row(session):
    run(session, [ti("A", due_date=date(2026, 3, 8))])
    t = all_tasks(session)[0]
    assert t.due_is_date_only and t.due_at == datetime(2026, 3, 9, 3, 59, 59, tzinfo=UTC)


def test_AC3_7_all_day_bounds_new_york():
    s, e = all_day_bounds(date(2026, 11, 20), date(2026, 11, 21), NY)
    assert (s, e) == (datetime(2026, 11, 20, 5, tzinfo=UTC), datetime(2026, 11, 21, 5, tzinfo=UTC))
    s, e = all_day_bounds(date(2026, 3, 8), date(2026, 3, 9), NY)  # 23 hour day
    assert e - s == timedelta(hours=23)


def test_AC3_8_event_end_before_start_rejected():
    a = datetime(2026, 1, 1, 10, tzinfo=UTC)
    with pytest.raises(ValidationError):
        EventIn(
            source="google_calendar",
            source_ref="x",
            calendar_id="c",
            title="t",
            start_at=a,
            end_at=a - timedelta(hours=1),
        )


def test_empty_title_rejected():
    with pytest.raises(ValidationError):
        TaskIn(title="   ", scope="a", source_ref="a")


def test_due_date_and_due_at_together_rejected():
    with pytest.raises(ValidationError):
        ti("x", due_date=date(2026, 1, 1), due_at=T0)


def test_naive_datetime_rejected():
    with pytest.raises(ValidationError):
        ti("x", due_at=datetime(2026, 1, 1))


def test_zoneinfo_used():
    assert ZoneInfo(NY)
