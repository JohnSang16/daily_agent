"""Read dated checkbox lines from the local vault into tasks. Read only, untrusted input."""

import logging
import os
import re
from datetime import UTC, date, datetime, time
from fnmatch import fnmatch
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SyncRun, Task
from app.schemas import TaskIn
from app.tasks_sync import sync_tasks

SOURCE = "obsidian"
log = logging.getLogger("obsidian")

LINE = re.compile(r"^\s*[-*]\s+\[([ xX])\]\s+(.*)$")
DUE = re.compile(r"📅\s*(\S+)(?:\s+(\d{1,2}:\d{2}))?")
SCHED = re.compile(r"⏳\s*\S+")
EFFORT = re.compile(r"\[effort::\s*(\d+)\s*([mh])\s*\]", re.I)
IMPORTANCE = re.compile(r"\[importance::\s*(\d+)\s*\]", re.I)


def parse_line(line: str, scope: str, lineno: int, tz: str) -> TaskIn | None:
    m = LINE.match(line)
    if not m or "📅" not in m.group(2):
        return None  # a checkbox with no due date is a checklist item, not a task
    body = m.group(2)
    review = None
    due_at = due_date = None
    d = DUE.search(body)
    try:
        day = date.fromisoformat(d.group(1))
        if d.group(2):
            h, mi = map(int, d.group(2).split(":"))
            due_at = datetime.combine(day, time(h, mi), ZoneInfo(tz)).astimezone(UTC)
        else:
            due_date = day
    except ValueError:
        review = "unreadable due date"
    effort = None
    if e := EFFORT.search(body):
        effort = int(e.group(1)) * (60 if e.group(2).lower() == "h" else 1)
    importance = None
    if i := IMPORTANCE.search(body):
        importance = int(i.group(1)) if 1 <= int(i.group(1)) <= 5 else None
        if importance is None:
            review = review or "importance must be 1 to 5"
    title = body
    for rx in (DUE, SCHED, EFFORT, IMPORTANCE):
        title = rx.sub("", title)
    title = " ".join(title.split())
    if not title:
        return None
    return TaskIn(
        title=title,
        scope=scope,
        source_ref=f"{scope}:{lineno}",
        due_at=due_at,
        due_date=due_date,
        effort_minutes=effort,
        importance=importance,
        done=m.group(1) in "xX",
        needs_review=review is not None,
        review_reason=review,
    )


def iter_notes(root: Path, ignore_globs, max_bytes: int, counts: dict | None = None):
    """Yields (relative path, Path) per readable note. Never follows a link out of the vault."""
    root = root.resolve()
    if not root.is_dir():
        raise FileNotFoundError("vault path is not a readable directory")
    for dirpath, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "node_modules"]
        for name in files:
            p = Path(dirpath) / name
            rel = p.relative_to(root).as_posix()
            if not name.endswith(".md") or name.startswith("."):
                continue
            if any(fnmatch(rel, g) for g in ignore_globs):
                continue
            if p.is_symlink() and not p.resolve().is_relative_to(root):
                continue
            if p.stat().st_size > max_bytes:
                if counts is not None:
                    counts["skipped_large"] += 1
                continue
            yield rel, p


def parse_vault(root: Path, tz: str, ignore_globs, max_bytes: int) -> tuple[dict, dict]:
    """Returns ({relative path: [TaskIn]}, counts)."""
    out, counts = {}, {"files": 0, "skipped_large": 0}
    for rel, p in iter_notes(root, ignore_globs, max_bytes, counts):
        counts["files"] += 1
        items = []
        for n, line in enumerate(p.read_text(errors="replace").splitlines(), 1):
            if t := parse_line(line, rel, n, tz):
                items.append(t)
        out[rel] = items
    return out, counts


def sync_obsidian(
    s: Session,
    vault_path,
    now: datetime,
    tz: str,
    ignore_globs=("templates/*", "archive/*"),
    max_bytes: int = 1_000_000,
    user_id: int = 1,
) -> int:
    """Upsert every dated task in the vault. A failed read changes nothing and logs an error run."""
    try:
        by_scope, counts = parse_vault(Path(vault_path), tz, ignore_globs, max_bytes)
        known = set(
            s.scalars(select(Task.scope).where(Task.source == SOURCE, Task.user_id == user_id))
        )
        changed = 0
        for scope in sorted(known | set(by_scope)):  # a vanished file empties its scope
            changed += sync_tasks(
                s, SOURCE, scope, by_scope.get(scope, []), now, tz, user_id=user_id
            )
        n = sum(len(v) for v in by_scope.values())
        s.add(
            SyncRun(
                source=SOURCE,
                started_at=now,
                finished_at=now,
                status="ok",
                items_seen=n,
                items_changed=changed,
            )
        )
        s.commit()
        log.info(
            "obsidian sync files=%d skipped_large=%d tasks=%d",
            counts["files"],
            counts["skipped_large"],
            n,
        )
        return changed
    except Exception as exc:
        s.rollback()
        s.add(
            SyncRun(
                source=SOURCE,
                started_at=now,
                finished_at=now,
                status="error",
                error_summary=type(exc).__name__,
            )
        )
        s.commit()
        raise
