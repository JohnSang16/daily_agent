"""Spec 18: the daily check-in and input and outcome goals. Local only, never logged or sent out."""

from datetime import date, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.auth import require_token
from app.clock import Clock, get_clock
from app.models import DailyCheckin, Goal, GoalLog

router = APIRouter(dependencies=[Depends(require_token)])
Text200 = Field(None, max_length=200)
CHECKIN_FIELDS = ("obstacle", "if_then", "top_task_title", "did_top", "why_not", "let_go")


def _today(request: Request, clock: Clock) -> date:
    return clock.now().astimezone(ZoneInfo(request.app.state.settings.user_timezone)).date()


def _checkin(c: DailyCheckin | None) -> dict:
    return {k: getattr(c, k) if c else None for k in CHECKIN_FIELDS}


class CheckinIn(BaseModel):
    obstacle: str | None = Text200
    if_then: str | None = Text200
    top_task_title: str | None = Text200
    did_top: bool | None = None
    why_not: str | None = Text200
    let_go: str | None = Text200


@router.get("/checkin/today")
def get_checkin(request: Request, clock: Clock = Depends(get_clock)):
    today = _today(request, clock)
    with request.app.state.session_factory() as db:
        y = db.get(DailyCheckin, (today - timedelta(days=1)).isoformat())
        since = (today - timedelta(days=14)).isoformat()
        answered = db.scalars(
            select(DailyCheckin.did_top).where(
                DailyCheckin.day >= since,
                DailyCheckin.day < today.isoformat(),
                DailyCheckin.did_top.is_not(None),
            )
        ).all()
        return {
            "date": today.isoformat(),
            "today": _checkin(db.get(DailyCheckin, today.isoformat())),
            "yesterday": {
                k: getattr(y, k) if y else None for k in ("top_task_title", "did_top", "why_not")
            },
            "say_do": {"kept": sum(answered), "of": len(answered)},
        }


@router.put("/checkin/today")
def put_checkin(body: CheckinIn, request: Request, clock: Clock = Depends(get_clock)):
    day = _today(request, clock).isoformat()
    with request.app.state.session_factory() as db:
        c = db.get(DailyCheckin, day) or DailyCheckin(day=day)
        for k, v in body.model_dump(exclude_unset=True).items():  # only the fields sent change
            setattr(c, k, v.strip() if isinstance(v, str) else v)
        c.updated_at = clock.now()
        db.merge(c)
        db.commit()
        return _checkin(db.get(DailyCheckin, day))


class GoalIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    kind: Literal["input", "outcome"]
    unit: str = Field("", max_length=20)
    target: int = Field(ge=1, le=10_000_000)
    current: int = Field(0, ge=0, le=10_000_000)


class GoalPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=60)
    target: int | None = Field(None, ge=1, le=10_000_000)
    current: int | None = Field(None, ge=0, le=10_000_000)


class CountIn(BaseModel):
    count: int = Field(ge=0, le=10_000)


def _goal(db, goal_id: int) -> Goal:
    g = db.get(Goal, goal_id)
    if g is None or g.archived:
        raise HTTPException(404, "not found")
    return g


def _view(g: Goal, logs: dict[str, int], today: date, tz: ZoneInfo) -> dict:
    out = {"id": g.id, "name": g.name, "kind": g.kind, "unit": g.unit, "target": g.target}
    if g.kind == "outcome":
        return {**out, "current": g.current}
    days = [(today - timedelta(days=n)).isoformat() for n in range(6, -1, -1)]
    last7 = [logs.get(d, 0) for d in days]
    created = g.created_at.astimezone(tz).date()
    # never miss twice: one missed day is fine, two in a row (both while the goal existed) is not
    missed_twice = created <= today - timedelta(days=2) and all(n < g.target for n in last7[-3:-1])
    month = (today - timedelta(days=29)).isoformat()
    return {
        **out,
        "today": last7[-1],
        "last7": last7,
        "hit7": sum(n >= g.target for n in last7),
        "missed_twice": missed_twice,
        "total30": sum(n for d, n in logs.items() if d >= month),
    }


@router.get("/goals")
def list_goals(request: Request, clock: Clock = Depends(get_clock)):
    today = _today(request, clock)
    tz = ZoneInfo(request.app.state.settings.user_timezone)
    with request.app.state.session_factory() as db:
        goals = db.scalars(select(Goal).where(Goal.archived.is_(False)).order_by(Goal.id)).all()
        since = (today - timedelta(days=29)).isoformat()
        logs: dict[int, dict[str, int]] = {}
        for log in db.scalars(select(GoalLog).where(GoalLog.day >= since)):
            logs.setdefault(log.goal_id, {})[log.day] = log.count
        return [_view(g, logs.get(g.id, {}), today, tz) for g in goals]


@router.post("/goals")
def create_goal(body: GoalIn, request: Request, clock: Clock = Depends(get_clock)):
    with request.app.state.session_factory() as db:
        g = Goal(**body.model_dump(), created_at=clock.now(), archived=False)
        db.add(g)
        db.commit()
        return {"id": g.id}


@router.patch("/goals/{goal_id}")
def patch_goal(goal_id: int, body: GoalPatch, request: Request):
    with request.app.state.session_factory() as db:
        g = _goal(db, goal_id)
        for k, v in body.model_dump(exclude_unset=True, exclude_none=True).items():
            setattr(g, k, v)
        db.commit()
    return {"id": goal_id}


@router.delete("/goals/{goal_id}")
def delete_goal(goal_id: int, request: Request):
    with request.app.state.session_factory() as db:
        _goal(db, goal_id).archived = True  # logs stay, so the history is never lost
        db.commit()
    return {"archived": goal_id}


@router.put("/goals/{goal_id}/today")
def log_today(goal_id: int, body: CountIn, request: Request, clock: Clock = Depends(get_clock)):
    day = _today(request, clock).isoformat()
    with request.app.state.session_factory() as db:
        _goal(db, goal_id)
        db.merge(GoalLog(goal_id=goal_id, day=day, count=body.count))
        db.commit()
    return {"id": goal_id, "date": day, "count": body.count}
