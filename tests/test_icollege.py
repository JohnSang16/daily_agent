import logging
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.allowlist import RULES
from app.db import Base, make_session_factory
from app.http_client import GuardedHttpClient, RequestDenied
from app.models import SyncRun, Task
from app.sources.icollege import sync_icollege

NY = "America/New_York"
NOW = datetime(2026, 11, 18, 14, 0, tzinfo=UTC)
URL = "https://gastate.view.usg.edu/d2l/le/calendar/feed/user/feed.ics?token=SUPERSECRETTOKEN"


def ev(summary, start, location="CSC 3210 Comp Org"):
    return (
        f"BEGIN:VEVENT\r\nSUMMARY:{summary}\r\nLOCATION:{location}\r\n"
        f"DTSTART:{start}\r\nEND:VEVENT\r\n"
    )


def feed(*events):
    return "BEGIN:VCALENDAR\r\n" + "".join(events) + "END:VCALENDAR\r\n"


@pytest.fixture
def s():
    sf = make_session_factory("sqlite://")
    Base.metadata.create_all(sf.kw["bind"])
    with sf() as db:
        yield db


def sync(s, text=None, fetch=None):
    return sync_icollege(s, fetch or (lambda: text), NOW, NY)


def tasks(s):
    return list(s.scalars(select(Task).order_by(Task.title)))


def test_AC6_1_three_future_due_events(s):
    sync(
        s,
        feed(
            ev("Project - Due", "20261204T045900Z"),
            ev("Quiz 5 - Due", "20261120T165900Z"),
            ev("HW 8 - Due", "20261125T045900Z"),
        ),
    )
    t = {x.title.split(" (")[0]: x.due_at for x in tasks(s)}
    assert t["Quiz 5"] == datetime(2026, 11, 20, 16, 59, tzinfo=UTC)
    assert len(t) == 3 and all(x.source == "icollege" and x.scope == "feed" for x in tasks(s))


def test_AC6_2_ignores_lectures_past_and_other(s):
    sync(
        s,
        feed(
            ev("Lecture", "20261120T160000Z"),
            ev("Old HW - Due", "20261101T045900Z"),
            ev("Real HW - Due", "20261125T045900Z"),
        ),
    )
    assert [x.title.split(" (")[0] for x in tasks(s)] == ["Real HW"]


def test_AC6_3_availability_ends(s):
    sync(s, feed(ev("Lab 3 - Availability Ends", "20261130T045900Z")))
    (t,) = tasks(s)
    assert "(closes)" in t.title


def test_AC6_4_folded_lines(s):
    folded = (
        "BEGIN:VEVENT\r\nSUMMARY:A very long homework na\r\n me here - Due\r\n"
        "DTSTART:20261125T045900Z\r\nEND:VEVENT\r\n"
    )
    sync(s, feed(folded))
    assert tasks(s)[0].title.startswith("A very long homework name here")


def test_AC6_5_idempotent(s):
    f = feed(ev("HW - Due", "20261125T045900Z"), ev("HW - Due", "20261126T045900Z"))
    sync(s, f)
    sync(s, f)
    assert len(tasks(s)) == 2


def test_AC6_6_removed_event_is_gone(s):
    sync(s, feed(ev("A - Due", "20261125T045900Z"), ev("B - Due", "20261126T045900Z")))
    sync(s, feed(ev("A - Due", "20261125T045900Z")))
    assert {x.title.split(" (")[0]: x.status for x in tasks(s)} == {"A": "open", "B": "gone"}


def test_AC6_7_failure_keeps_data_and_hides_url(s):
    sync(s, feed(ev("A - Due", "20261125T045900Z")))

    def boom():
        raise RuntimeError(URL)

    with pytest.raises(RuntimeError):
        sync(s, fetch=boom)
    assert [x.status for x in tasks(s)] == ["open"]
    last = s.scalars(select(SyncRun).order_by(SyncRun.id.desc())).first()
    assert last.status == "error" and "SUPERSECRETTOKEN" not in (last.error_summary or "")
    assert last.error_summary == "RuntimeError"


def test_AC6_8_allowlist():
    class Sink:
        def record(self, *a, **k):
            pass

    http = GuardedHttpClient(Sink(), rules=RULES, transport=None)
    with pytest.raises(RequestDenied):
        http.get("icollege", "https://gastate.view.usg.edu/d2l/home")
    assert any(r.integration == "icollege" and r.host == "gastate.view.usg.edu" for r in RULES)


def test_AC6_9_logs_clean(s, caplog):
    with caplog.at_level(logging.DEBUG):
        sync(s, feed(ev("SECRETHOMEWORKNAME - Due", "20261125T045900Z")))
    assert "SECRETHOMEWORKNAME" not in caplog.text and "SUPERSECRETTOKEN" not in caplog.text
