"""Read Google Calendar events into the shared events table. Read only, no descriptions stored."""

import json
import time
from datetime import UTC, date, datetime, timedelta
from datetime import time as dtime
from pathlib import Path
from typing import Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Event, SyncRun
from app.schemas import EventIn
from app.tasks_sync import all_day_bounds

SOURCE = "google_calendar"
API = "https://www.googleapis.com/calendar/v3/calendars"
TOKEN_URL = "https://oauth2.googleapis.com/token"


class RateLimited(Exception):
    pass


class GoogleCalendarClient(Protocol):
    def list_events(
        self,
        calendar_id: str,
        time_min: datetime,
        time_max: datetime,
        page_token: str | None = None,
    ) -> tuple[list[dict], str | None]: ...


class HttpCalendarClient:
    """Real client. All traffic goes through the guarded HTTP client (allowlisted)."""

    def __init__(self, http, secrets_path: str, token_path: str):
        self.http, self.token_path = http, Path(token_path)
        c = json.loads(Path(secrets_path).read_text())
        self.client = c.get("installed") or c["web"]
        self.token = json.loads(self.token_path.read_text())

    def _refresh(self):
        r = self.http.request(
            "google_oauth",
            "POST",
            TOKEN_URL,
            data={
                "client_id": self.client["client_id"],
                "client_secret": self.client["client_secret"],
                "refresh_token": self.token["refresh_token"],
                "grant_type": "refresh_token",
            },
        )
        r.raise_for_status()  # invalid_grant here means the 7 day Testing token expired
        self.token["access_token"] = r.json()["access_token"]
        self.token_path.write_text(json.dumps(self.token))
        self.token_path.chmod(0o600)

    def list_events(self, calendar_id, time_min, time_max, page_token=None):
        params = {
            "timeMin": time_min.isoformat(),
            "timeMax": time_max.isoformat(),
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": 250,
            "fields": "nextPageToken,items(id,summary,start,end,location,status,transparency,"
            "attendees(self,responseStatus))",
        }
        if page_token:
            params["pageToken"] = page_token
        url = f"{API}/{calendar_id.replace('@', '%40')}/events"
        for attempt in (0, 1):
            h = {"Authorization": f"Bearer {self.token.get('access_token', '')}"}
            r = self.http.get(SOURCE, url, params=params, headers=h)
            if r.status_code == 401 and attempt == 0:
                self._refresh()
                continue
            break
        if r.status_code in (403, 429):
            raise RateLimited()
        r.raise_for_status()
        body = r.json()
        return body.get("items", []), body.get("nextPageToken")


def _parse(raw: dict, calendar_id: str, tz: str) -> EventIn | None:
    if any(
        a.get("self") and a.get("responseStatus") == "declined" for a in raw.get("attendees", [])
    ):
        return None
    st, en = raw.get("start"), raw.get("end")
    if not st or not en:  # cancelled stubs can arrive with no times
        return None
    all_day = "date" in st
    if all_day:
        start, end = all_day_bounds(
            date.fromisoformat(st["date"]), date.fromisoformat(en["date"]), tz
        )
    else:
        start = datetime.fromisoformat(st["dateTime"]).astimezone(UTC)
        end = datetime.fromisoformat(en["dateTime"]).astimezone(UTC)
    return EventIn(
        source=SOURCE,
        source_ref=raw["id"],
        calendar_id=calendar_id,
        title=(raw.get("summary") or "").strip() or "Busy",
        start_at=start,
        end_at=end,
        all_day=all_day,
        busy=raw.get("transparency") != "transparent",
        status="cancelled"
        if raw.get("status") == "cancelled"
        else "tentative"
        if raw.get("status") == "tentative"
        else "confirmed",
        location=raw.get("location"),
    )


def _fetch(client, cal, tmin, tmax, sleep, max_retries):
    out, token = [], None
    while True:
        for attempt in range(max_retries + 1):
            try:
                items, token = client.list_events(cal, tmin, tmax, token)
                break
            except RateLimited:
                if attempt == max_retries:
                    raise
                sleep(2**attempt)  # 1, 2, 4 seconds
        out += items
        if not token:
            return out


def sync_google_calendar(
    s: Session,
    client: GoogleCalendarClient,
    now: datetime,
    tz: str,
    calendar_ids: tuple[str, ...] = ("primary",),
    past_days: int = 1,
    ahead_days: int = 14,
    sleep=time.sleep,
    max_retries: int = 3,
    user_id: int = 1,
) -> int:
    """Upsert the window. On any failure existing rows stay untouched and an error run is logged."""
    z = ZoneInfo(tz)
    midnight = datetime.combine(now.astimezone(z).date(), dtime(), z)
    tmin = (midnight - timedelta(days=past_days)).astimezone(UTC)
    tmax = (midnight + timedelta(days=ahead_days + 1)).astimezone(UTC)
    run = SyncRun(source=SOURCE, started_at=now, status="error")
    s.add(run)
    try:
        parsed = []
        for cal in calendar_ids:
            for raw in _fetch(client, cal, tmin, tmax, sleep, max_retries):
                e = _parse(raw, cal, tz)
                if e:
                    parsed.append(e)
        existing = {
            (e.calendar_id, e.source_ref, e.start_at): e
            for e in s.scalars(
                select(Event).where(
                    Event.user_id == user_id,
                    Event.source == SOURCE,
                    Event.calendar_id.in_(calendar_ids),
                    Event.start_at >= tmin,
                    Event.start_at < tmax,
                )
            )
        }
        changed, seen = 0, set()
        for e in parsed:
            key = (e.calendar_id, e.source_ref, e.start_at)
            seen.add(key)
            row = existing.get(key)
            fields = e.model_dump(exclude={"source", "source_ref", "calendar_id"})
            if row is None:
                s.add(
                    Event(
                        user_id=user_id,
                        source=SOURCE,
                        source_ref=e.source_ref,
                        calendar_id=e.calendar_id,
                        updated_at=now,
                        last_seen_at=now,
                        **fields,
                    )
                )
                changed += 1
            else:
                if any(getattr(row, k) != v for k, v in fields.items()):
                    for k, v in fields.items():
                        setattr(row, k, v)
                    row.updated_at = now
                    changed += 1
                row.last_seen_at = now
        for key, row in existing.items():
            if key not in seen and row.status != "cancelled":
                row.status, row.updated_at = "cancelled", now
                changed += 1
        run.status, run.items_seen, run.items_changed, run.finished_at = (
            "ok",
            len(parsed),
            changed,
            now,
        )
        s.commit()
        return changed
    except Exception as exc:
        s.rollback()
        s.add(
            SyncRun(
                source=SOURCE,
                started_at=now,
                finished_at=now,
                status="error",
                error_summary=f"{type(exc).__name__}: {exc}"[:500],
            )
        )
        s.commit()
        raise
