"""Turn the iCollege (D2L) calendar feed into tasks. Exact due dates, no LLM, URL stays private."""

import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import SyncRun
from app.schemas import TaskIn
from app.tasks_sync import sync_tasks

SOURCE, SCOPE = "icollege", "feed"
log = logging.getLogger("icollege")
SUFFIX = re.compile(r"\s*-\s*(Due|Availability Ends)\s*$", re.I)


def _field(block: str, key: str) -> str:
    m = re.search(rf"^{key}[^:\n]*:(.*)$", block, re.M)
    return m.group(1).strip().replace("\\,", ",") if m else ""


def parse_feed(text: str, now: datetime, keep_overdue_days: int = 14) -> list[TaskIn]:
    """Future due items, plus ones missed in the last keep_overdue_days (they show as overdue)."""
    text = re.sub(r"\r?\n[ \t]", "", text)  # unfold wrapped lines
    out = []
    for blk in text.split("BEGIN:VEVENT")[1:]:
        summary, loc, start = (
            _field(blk, "SUMMARY"),
            _field(blk, "LOCATION"),
            _field(blk, "DTSTART"),
        )
        m = SUFFIX.search(summary)
        if not m:
            continue
        try:
            due = datetime.strptime(start, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
        except ValueError:
            continue  # floating or date only starts are not exact due moments
        if due <= now - timedelta(days=keep_overdue_days):
            continue
        title = SUFFIX.sub("", summary).strip()
        if m.group(1).lower().startswith("availability"):
            title += " (closes)"
        if loc:
            title += f" ({loc[:40]})"
        out.append(TaskIn(title=title, scope=SCOPE, source_ref=SCOPE, due_at=due))
    return out


def http_feed_fetch(http, url_path: str) -> Callable[[], str]:
    """Reads the private URL from a local file at call time; the URL never leaves this function."""

    def fetch() -> str:
        url = Path(url_path).expanduser().read_text().strip()
        r = http.get("icollege", url)
        r.raise_for_status()
        return r.text

    return fetch


def sync_icollege(
    s: Session, fetch: Callable[[], str], now: datetime, tz: str, user_id: int = 1
) -> int:
    try:
        items = parse_feed(fetch(), now)
        changed = sync_tasks(s, SOURCE, SCOPE, items, now, tz, user_id=user_id)
        s.add(
            SyncRun(
                source=SOURCE,
                started_at=now,
                finished_at=now,
                status="ok",
                items_seen=len(items),
                items_changed=changed,
            )
        )
        s.commit()
        log.info("icollege sync tasks=%d changed=%d", len(items), changed)
        return changed
    except Exception as exc:
        s.rollback()
        s.add(
            SyncRun(
                source=SOURCE,
                started_at=now,
                finished_at=now,
                status="error",
                error_summary=type(exc).__name__,  # class only: messages can hold the URL
            )
        )
        s.commit()
        raise
