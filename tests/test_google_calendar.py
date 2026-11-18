from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.db import Base, make_session_factory
from app.models import Event, SyncRun
from app.sources.google_calendar import RateLimited, sync_google_calendar

NY = "America/New_York"
NOW = datetime(2026, 11, 16, 14, 0, tzinfo=UTC)  # Mon 09:00 New York


class FakeClient:
    """pages: list of item lists, one per page. fail: exception to raise instead."""

    def __init__(self, pages, fail=None, rate_limits=0):
        self.pages, self.fail, self.rate_limits, self.calls = pages, fail, rate_limits, 0

    def list_events(self, calendar_id, time_min, time_max, page_token=None):
        self.calls += 1
        if self.rate_limits > 0:
            self.rate_limits -= 1
            raise RateLimited()
        if self.fail:
            raise self.fail
        i = int(page_token or 0)
        nxt = str(i + 1) if i + 1 < len(self.pages) else None
        return self.pages[i], nxt


def ev(id, title="Class", start="2026-11-17T09:00:00-05:00", end="2026-11-17T10:00:00-05:00", **kw):
    return {
        "id": id,
        "summary": title,
        "start": {"dateTime": start},
        "end": {"dateTime": end},
        **kw,
    }


@pytest.fixture
def s():
    sf = make_session_factory("sqlite://")
    Base.metadata.create_all(sf.kw["bind"])
    with sf() as db:
        yield db


def sync(s, client, sleeps=None, **kw):
    return sync_google_calendar(
        s, client, NOW, NY, sleep=(sleeps.append if sleeps is not None else lambda _: None), **kw
    )


def rows(s):
    return list(s.scalars(select(Event).order_by(Event.start_at, Event.source_ref)))


def test_AC4_1_three_events_utc(s):
    sync(
        s,
        FakeClient(
            [
                [
                    ev("a"),
                    ev("b", start="2026-11-17T13:00:00-05:00", end="2026-11-17T14:00:00-05:00"),
                    ev("c", location="Rm 5"),
                ]
            ]
        ),
    )
    r = rows(s)
    assert len(r) == 3
    assert r[0].start_at == datetime(2026, 11, 17, 14, tzinfo=UTC)  # 09:00 EST
    assert {e.location for e in r} == {None, "Rm 5"}
    assert all(e.source == "google_calendar" and e.calendar_id == "primary" for e in r)


def test_AC4_2_all_day(s):
    sync(
        s,
        FakeClient(
            [
                [
                    {
                        "id": "d",
                        "summary": "Holiday",
                        "start": {"date": "2026-11-26"},
                        "end": {"date": "2026-11-27"},
                    }
                ]
            ]
        ),
    )
    (e,) = rows(s)
    assert e.all_day
    assert e.start_at == datetime(2026, 11, 26, 5, tzinfo=UTC)  # midnight New York
    assert e.end_at == datetime(2026, 11, 27, 5, tzinfo=UTC)


def test_AC4_3_recurring_instances_distinct(s):
    sync(
        s,
        FakeClient(
            [
                [
                    ev(
                        "rec_20261117",
                        start="2026-11-17T09:00:00-05:00",
                        end="2026-11-17T10:00:00-05:00",
                        recurringEventId="rec",
                    ),
                    ev(
                        "rec_20261124",
                        start="2026-11-24T09:00:00-05:00",
                        end="2026-11-24T10:00:00-05:00",
                        recurringEventId="rec",
                    ),
                ]
            ]
        ),
    )
    assert len(rows(s)) == 2


def test_AC4_4_declined_excluded_transparent_not_busy(s):
    declined = ev("x", attendees=[{"self": True, "responseStatus": "declined"}])
    free = ev("y", transparency="transparent")
    sync(s, FakeClient([[declined, free]]))
    (e,) = rows(s)
    assert e.source_ref == "y" and e.busy is False


def test_missing_title_is_busy_and_cancelled_kept(s):
    no_title = ev("n")
    del no_title["summary"]
    sync(s, FakeClient([[no_title, ev("z", status="cancelled")]]))
    by = {e.source_ref: e for e in rows(s)}
    assert by["n"].title == "Busy"
    assert by["z"].status == "cancelled"


def test_AC4_5_idempotent(s):
    c = [[ev("a"), ev("b")]]
    sync(s, FakeClient(c))
    sync(s, FakeClient(c))
    assert len(rows(s)) == 2


def test_AC4_6_deleted_upstream_cancelled(s):
    sync(s, FakeClient([[ev("a"), ev("b")]]))
    sync(s, FakeClient([[ev("a")]]))
    by = {e.source_ref: e.status for e in rows(s)}
    assert by == {"a": "confirmed", "b": "cancelled"}


def test_AC4_7_error_keeps_data_and_logs(s):
    sync(s, FakeClient([[ev("a")]]))
    with pytest.raises(RuntimeError):
        sync(s, FakeClient([], fail=RuntimeError("boom")))
    assert [e.status for e in rows(s)] == ["confirmed"]
    last = s.scalars(select(SyncRun).order_by(SyncRun.id.desc())).first()
    assert (
        last.status == "error" and last.error_summary == "RuntimeError"
    )  # class only, no message text


def test_AC4_8_rate_limit_backoff_then_ok(s):
    sleeps = []
    sync(s, FakeClient([[ev("a")]], rate_limits=2), sleeps=sleeps)
    assert sleeps == [1, 2] and len(rows(s)) == 1


def test_AC4_8_rate_limit_cap_fails_cleanly(s):
    sleeps, c = [], FakeClient([[ev("a")]], rate_limits=99)
    with pytest.raises(RateLimited):
        sync(s, c, sleeps=sleeps, max_retries=3)
    assert c.calls == 4 and len(sleeps) == 3
    assert s.scalars(select(SyncRun)).one().status == "error"


def test_AC4_9_pagination(s):
    sync(s, FakeClient([[ev("a")], [ev("b")]]))
    assert len(rows(s)) == 2


def test_AC4_10_no_description_or_attendees_stored(s):
    sync(
        s,
        FakeClient(
            [[ev("a", description="SECRET-BODY", attendees=[{"email": "x@y.com", "self": False}])]]
        ),
    )
    cols = {c.name for c in Event.__table__.columns}
    assert not {"description", "attendees", "attendee_emails"} & cols
    (e,) = rows(s)
    assert "SECRET-BODY" not in repr(vars(e)) and "x@y.com" not in repr(vars(e))


def test_ok_sync_run_recorded(s):
    sync(s, FakeClient([[ev("a")]]))
    r = s.scalars(select(SyncRun)).one()
    assert r.source == "google_calendar" and r.status == "ok" and r.items_seen == 1
