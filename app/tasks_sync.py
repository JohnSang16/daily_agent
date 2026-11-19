"""Upsert a source's tasks into the shared table, and the time conversions it needs."""

import hashlib
import re
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Task
from app.schemas import TaskIn

_MARKERS = re.compile(r"^\s*([-*+]\s+)?(\[[ xX]\]\s*)?")


def normalize_title(title: str) -> str:
    t = _MARKERS.sub("", title)
    return re.sub(r"\s+", " ", t).strip().lower()


def fingerprint(source: str, scope: str, title: str, occurrence: int) -> str:
    raw = "\x1f".join([source, scope, normalize_title(title), str(occurrence)])
    return hashlib.sha256(raw.encode()).hexdigest()


def date_only_due_to_utc(d: date, tz: str) -> datetime:
    return datetime.combine(d, time(23, 59, 59), ZoneInfo(tz)).astimezone(UTC)


def all_day_bounds(start: date, end_exclusive: date, tz: str) -> tuple[datetime, datetime]:
    z = ZoneInfo(tz)
    return (
        datetime.combine(start, time(), z).astimezone(UTC),
        datetime.combine(end_exclusive, time(), z).astimezone(UTC),
    )


def sync_tasks(
    s: Session,
    source: str,
    scope: str,
    items: list[TaskIn],
    now: datetime,
    tz: str,
    success: bool = True,
    user_id: int = 1,
) -> int:
    """Upsert items for one source scope. Returns rows changed. A failed sync changes nothing."""
    if not success:
        return 0
    existing = {
        t.fingerprint: t
        for t in s.scalars(
            select(Task).where(Task.user_id == user_id, Task.source == source, Task.scope == scope)
        )
    }
    seen: set[str] = set()
    counts: dict[str, int] = {}
    changed = 0
    for it in items:
        norm = normalize_title(it.title)
        n = counts[norm] = counts.get(norm, 0) + 1
        fp = fingerprint(source, scope, it.title, n)
        seen.add(fp)
        date_only = it.due_date is not None
        due = date_only_due_to_utc(it.due_date, tz) if date_only else it.due_at
        status = "done" if it.done else "open"
        t = existing.get(fp)
        if t is None:
            s.add(
                Task(
                    user_id=user_id,
                    source=source,
                    scope=scope,
                    source_ref=it.source_ref,
                    fingerprint=fp,
                    title=it.title,
                    due_at=due,
                    due_is_date_only=date_only,
                    effort_minutes=it.effort_minutes,
                    importance=it.importance,
                    status=status,
                    needs_review=it.needs_review,
                    review_reason=it.review_reason,
                    created_at=now,
                    updated_at=now,
                    last_seen_at=now,
                )
            )
            changed += 1
            continue
        # fields the source owns; snoozed_until and a locally set importance are never touched
        new = dict(
            title=it.title,
            source_ref=it.source_ref,
            due_at=due,
            due_is_date_only=date_only,
            effort_minutes=it.effort_minutes,
            status="done" if t.locally_done else status,  # marked done in the app: stays done
            needs_review=it.needs_review,
            review_reason=it.review_reason,
        )
        if t.importance is None:
            new["importance"] = it.importance
        if any(getattr(t, k) != v for k, v in new.items()):
            for k, v in new.items():
                setattr(t, k, v)
            t.updated_at = now
            changed += 1
        t.last_seen_at = now
    for fp, t in existing.items():
        if fp not in seen and t.status != "gone":
            t.status, t.updated_at = "gone", now
            changed += 1
    s.commit()
    return changed
