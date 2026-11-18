from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select

from app.auth import require_token
from app.clock import Clock, get_clock
from app.llm.explain import build_payload, explain
from app.models import Event, SyncRun, Task
from app.priority.engine import Config, EventView, TaskView, rank

router = APIRouter(dependencies=[Depends(require_token)])


def iso(dt: datetime | None) -> str | None:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None


def _block(b):
    return {"start": iso(b[0]), "end": iso(b[1])} if b else None


def _warnings(db, now: datetime, stale_hours: int, review_count: int) -> list[dict]:
    out = []
    runs = db.scalars(select(SyncRun).order_by(SyncRun.started_at)).all()
    latest, last_ok = {}, {}
    for r in runs:
        latest[r.source] = r
        if r.status == "ok":
            last_ok[r.source] = r
    for src, r in last_ok.items():
        age = now - (r.finished_at or r.started_at)
        if age > timedelta(hours=stale_hours):
            out.append(
                {
                    "code": "SOURCE_STALE",
                    "source": src,
                    "detail": f"last success {int(age.total_seconds() // 3600)}h ago",
                }
            )
    for src, r in latest.items():
        if r.status == "error":
            out.append({"code": "SYNC_ERROR", "source": src, "detail": "latest sync failed"})
    if review_count:
        out.append({"code": "NEEDS_REVIEW", "source": None, "detail": f"{review_count} to review"})
    return out


@router.get("/today")
def today(
    request: Request,
    date_: date | None = Query(None, alias="date"),
    limit: int = Query(10, ge=1, le=50),
    clock: Clock = Depends(get_clock),
):
    st = request.app.state.settings
    tz = ZoneInfo(st.user_timezone)
    now = clock.now()
    day = date_ or now.astimezone(tz).date()
    day_start = datetime.combine(day, time(), tz).astimezone(UTC)
    day_end = datetime.combine(day + timedelta(days=1), time(), tz).astimezone(UTC)
    cfg = Config(st.user_timezone, st.work_start, st.work_end, st.default_effort_minutes)

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
        items = [
            {
                "id": r.task_id,
                "rank": r.rank,
                "title": by_id[r.task_id].title,
                "due_at": iso(by_id[r.task_id].due_at),
                "source": by_id[r.task_id].source,
                "reasons": r.reasons,
                "at_risk": r.at_risk,
                "needs_review": by_id[r.task_id].needs_review,
            }
            for r in result.ranked
        ]
        review_count = sum(i["needs_review"] for i in items)
        local_midnight = datetime.combine(now.astimezone(tz).date(), time(), tz).astimezone(UTC)
        text, source, exhausted = explain(
            db,
            request.app.state.llm,
            st.llm_model,
            st.llm_daily_token_budget,
            build_payload(items[:5]),
            now,
            local_midnight,
        )
        warnings = _warnings(db, now, st.stale_after_hours, review_count)
        if exhausted:
            warnings.append(
                {
                    "code": "LLM_BUDGET_EXHAUSTED",
                    "source": None,
                    "detail": "daily token budget reached",
                }
            )
        todays = [e for e in events if e.start_at < day_end and e.end_at > day_start]

    top = None
    if items:
        top = {k: items[0][k] for k in ("id", "title", "due_at", "reasons", "at_risk")}
        top["suggested_block"] = _block(result.suggested_block)
    return {
        "date": day.isoformat(),
        "timezone": st.user_timezone,
        "generated_at": iso(now),
        "top_task": top,
        "ranked": items[:limit],
        "events": [
            {"title": e.title, "start": iso(e.start_at), "end": iso(e.end_at), "all_day": e.all_day}
            for e in sorted(todays, key=lambda e: e.start_at)
        ],
        "free_blocks": [_block(b) for b in result.free_blocks_today],
        "explanation": {"text": text, "source": source},
        "warnings": warnings,
        "needs_review_count": review_count,
    }
