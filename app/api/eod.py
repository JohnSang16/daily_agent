"""The nightly wrap: a few bullets in my own words, written verbatim into the vault's
daily-agent-logs/ folder alongside what the app already knows (tasks finished, today's goal)."""

from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select

from app.auth import require_token
from app.clock import Clock, get_clock
from app.models import DailyGoal, EodEntry, Task
from app.sources.vault_checkout import write_eod_log

router = APIRouter(dependencies=[Depends(require_token)])


def _today(request: Request, clock: Clock):
    return clock.now().astimezone(ZoneInfo(request.app.state.settings.user_timezone)).date()


def _tasks_done_today(db, tz: ZoneInfo, today) -> int:
    local_midnight = datetime.combine(today, time(), tz).astimezone(UTC)
    return db.scalar(
        select(func.count(Task.id)).where(
            Task.locally_done.is_(True),
            Task.status == "done",
            Task.updated_at >= local_midnight,
        )
    )


def _goal_text(db, today) -> str | None:
    g = db.get(DailyGoal, today.isoformat())
    return g.text if g else None


class EodIn(BaseModel):
    bullets: str = Field(min_length=1, max_length=4000)

    @field_validator("bullets")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("bullets can't be blank")
        return v


@router.get("/eod/today")
def get_eod(request: Request, clock: Clock = Depends(get_clock)):
    today = _today(request, clock)
    tz = ZoneInfo(request.app.state.settings.user_timezone)
    with request.app.state.session_factory() as db:
        e = db.get(EodEntry, today.isoformat())
        return {
            "date": today.isoformat(),
            "answered": e is not None,
            "bullets": e.bullets if e else None,
            "tasks_done_today": _tasks_done_today(db, tz, today),
            "goal": _goal_text(db, today),
        }


@router.put("/eod/today")
def put_eod(body: EodIn, request: Request, clock: Clock = Depends(get_clock)):
    today = _today(request, clock)
    tz = ZoneInfo(request.app.state.settings.user_timezone)
    now = clock.now()
    bullets = body.bullets
    with request.app.state.session_factory() as db:
        done = _tasks_done_today(db, tz, today)
        goal = _goal_text(db, today)
        db.merge(EodEntry(day=today.isoformat(), bullets=bullets, logged_at=now))
        db.commit()
    content = (
        f"# {today.isoformat()}\n\n"
        f"tasks done: {done}\n"
        f"goal: {goal or '(none set)'}\n\n"
        f"{bullets}\n"
    )
    write_eod_log(request.app.state.settings.obsidian_vault_path, today.isoformat(), content)
    return {"date": today.isoformat(), "answered": True, "bullets": bullets}
