"""GET /digest: the daily brief. Hard deadlines only, capped at seven, plus the standing lines."""

from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select

from app.api.today import _warnings, iso
from app.auth import require_token
from app.clock import Clock, get_clock
from app.digest import read_identity, read_lines, read_plan_from_vault, read_why_from_vault
from app.llm.explain import format_due
from app.models import Event, Task
from app.priority.engine import Config, EventView, TaskView, rank
from app.sources.vault_checkout import resolved_vault_path

router = APIRouter(dependencies=[Depends(require_token)])
CAP = 7


def _note(w: dict) -> str:
    src = (w.get("source") or "a source").replace("_", " ")
    if w["code"] == "SOURCE_STALE":
        return f"{src} is out of date"
    if w["code"] == "SYNC_ERROR":
        return f"{src} failed its last sync"
    return w.get("detail") or w["code"].lower()


@router.get("/digest")
def digest(request: Request, clock: Clock = Depends(get_clock)):
    st, now = request.app.state.settings, clock.now()
    tz = ZoneInfo(st.user_timezone)
    cfg = Config(
        st.user_timezone,
        st.work_start,
        st.work_end,
        st.default_effort_minutes,
        stale_overdue_days=st.stale_overdue_days,
    )
    with request.app.state.session_factory() as db:
        tasks = db.scalars(select(Task).where(Task.status == "open")).all()
        events = db.scalars(select(Event).where(Event.status != "cancelled")).all()
        result = rank(
            [
                TaskView(
                    t.id,
                    t.due_at,
                    t.effort_minutes,
                    t.importance,
                    t.created_at,
                    t.status,
                    t.snoozed_until,
                    t.needs_review,
                )
                for t in tasks
            ],
            [EventView(e.start_at, e.end_at, e.busy, e.status) for e in events],
            now,
            cfg,
        )
        by_id = {t.id: t for t in tasks}
        dated = [by_id[r.task_id] for r in result.ranked if by_id[r.task_id].due_at]
        notes = [_note(w) for w in _warnings(db, now, st.stale_after_hours, 0)]
        if result.stale_ids:
            n = len(result.stale_ids)
            notes.append(
                f"{n} overdue item{'s' if n != 1 else ''} older than "
                f"{st.stale_overdue_days} days hidden"
            )
    vault_path = resolved_vault_path(st)
    lines = read_lines(vault_path)
    today = now.astimezone(tz).date().isoformat()
    past = dated[CAP - 1].due_at.astimezone(tz) if len(dated) > CAP else None
    return {
        "date": today,
        "generated_at": iso(now),
        "mantra": lines.get("mantra"),
        "vision": lines.get("vision"),
        "why": read_why_from_vault(vault_path),
        "identity": read_identity(vault_path),
        "plan": read_plan_from_vault(vault_path, today),
        "deadlines": [
            {
                "id": t.id,
                "title": t.title,
                "due_at": iso(t.due_at),
                "due_local": format_due(iso(t.due_at), st.user_timezone),
            }
            for t in dated[:CAP]
        ],
        "overflow": max(0, len(dated) - CAP),
        "overflow_after": f"{past:%a %b} {past.day}" if past else None,
        "notes": notes,
    }
