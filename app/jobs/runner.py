"""Run source syncs safely: one at a time per source, errors recorded, never fatal to the rest."""

import threading
import time
from collections.abc import Callable
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import Clock
from app.config import Settings
from app.models import SyncRun
from app.sources.google_calendar import HttpCalendarClient, sync_google_calendar
from app.sources.icollege import http_feed_fetch, sync_icollege
from app.sources.obsidian import sync_obsidian

Source = Callable[[Session, datetime], int]

# hours without a success before /today warns (spec 09)
STALE_HOURS = {"google_calendar": 1, "obsidian": 1, "icollege": 6, "gmail_digest": 6}


def stale_hours_for(source: str, default: int) -> int:
    return STALE_HOURS.get(source, default)


def default_sources(settings: Settings, http) -> dict[str, Source]:
    def calendar(s, now):
        client = HttpCalendarClient(
            http, settings.google_client_secrets_path, settings.google_token_path
        )
        ids = tuple(c.strip() for c in settings.calendar_ids.split(",") if c.strip())
        return sync_google_calendar(s, client, now, settings.user_timezone, calendar_ids=ids)

    def obsidian(s, now):
        if not settings.obsidian_vault_path:
            raise FileNotFoundError("OBSIDIAN_VAULT_PATH is not set")
        globs = tuple(g.strip() for g in settings.obsidian_ignore_globs.split(",") if g.strip())
        return sync_obsidian(
            s, settings.obsidian_vault_path, now, settings.user_timezone, ignore_globs=globs
        )

    def icollege(s, now):
        fetch = http_feed_fetch(http, settings.icollege_feed_url_path)
        return sync_icollege(s, fetch, now, settings.user_timezone)

    return {"google_calendar": calendar, "obsidian": obsidian, "icollege": icollege}


class Runner:
    # ponytail: in process locks, fine for one process. Use a DB advisory lock if we ever scale out.
    def __init__(self, session_factory, sources: dict[str, Source], clock: Clock):
        self.sf, self.sources, self.clock = session_factory, sources, clock
        self._locks = {n: threading.Lock() for n in sources}

    def run_sync(self, name: str) -> dict:
        lock = self._locks[name]  # KeyError for an unknown source
        if not lock.acquire(blocking=False):
            return {"status": "already_running"}
        try:
            return self._run(name)
        finally:
            lock.release()

    def run_all(self) -> dict:
        return {n: self.run_sync(n) for n in self.sources}

    def _run(self, name: str) -> dict:
        t0, now = time.monotonic(), self.clock.now()
        with self.sf() as s:
            last = (
                s.scalars(
                    select(SyncRun.id).where(SyncRun.source == name).order_by(SyncRun.id.desc())
                ).first()
                or 0
            )
            status, changed, err = "ok", 0, None
            try:
                changed = self.sources[name](s, now)
            except Exception as exc:  # a failing source must never stop the others
                s.rollback()
                status, err = "error", type(exc).__name__  # class only, never message text
            row = s.scalars(
                select(SyncRun)
                .where(SyncRun.source == name, SyncRun.id > last)
                .order_by(SyncRun.id.desc())
            ).first()
            if row is None:
                row = SyncRun(
                    source=name,
                    started_at=now,
                    finished_at=now,
                    status=status,
                    items_changed=changed,
                    error_summary=err,
                )
                s.add(row)
            row.duration_ms = int((time.monotonic() - t0) * 1000)
            s.commit()
        return {"status": status, "changed": changed}


def scheduler_loop(run: Callable[[], object], interval_s: float, stop: threading.Event) -> None:
    while True:
        run()
        if stop.wait(interval_s):
            return
