"""Local only writes (my own database): manual items, goal, reminders upload, snooze, done."""

import hashlib
import uuid
from datetime import UTC, date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError

from app.auth import require_token
from app.clock import Clock, get_clock
from app.models import DailyGoal, Event, Task
from app.schemas import EventIn, TaskIn
from app.tasks_sync import date_only_due_to_utc, sync_tasks

router = APIRouter(dependencies=[Depends(require_token)])


def _due(v: str | None) -> tuple[datetime | None, date | None]:
    """ISO date -> (None, date). ISO date time with an offset -> (aware datetime, None)."""
    if not v:
        return None, None
    try:
        if len(v) == 10:
            return None, date.fromisoformat(v)
        d = datetime.fromisoformat(v)
    except ValueError:
        raise HTTPException(422, "bad date") from None
    if d.tzinfo is None:
        raise HTTPException(422, "date time needs an offset")
    return d.astimezone(UTC), None


class ItemIn(BaseModel):
    kind: Literal["task", "event"]
    title: str
    due: str | None = None
    effort_minutes: int | None = None
    importance: int | None = None
    start: datetime | None = None
    end: datetime | None = None
    all_day: bool = False


@router.post("/items")
def create_item(body: ItemIn, request: Request, clock: Clock = Depends(get_clock)):
    now, ref = clock.now(), uuid.uuid4().hex
    tz = request.app.state.settings.user_timezone
    with request.app.state.session_factory() as db:
        try:
            if body.kind == "task":
                at, day = _due(body.due)
                it = TaskIn(
                    title=body.title,
                    scope="manual",
                    source_ref=ref,
                    due_at=at,
                    due_date=day,
                    effort_minutes=body.effort_minutes,
                    importance=body.importance,
                )
                row = Task(
                    user_id=1,
                    source="manual",
                    scope="manual",
                    source_ref=ref,
                    fingerprint=hashlib.sha256(ref.encode()).hexdigest(),
                    title=it.title,
                    due_at=date_only_due_to_utc(day, tz) if day else at,
                    due_is_date_only=day is not None,
                    effort_minutes=it.effort_minutes,
                    importance=it.importance,
                    status="open",
                    needs_review=False,
                    created_at=now,
                    updated_at=now,
                    last_seen_at=now,
                )
                db.add(row)
                db.commit()
                return {"id": f"task-{row.id}"}
            if not body.start or not body.end:
                raise HTTPException(422, "event needs start and end")
            e = EventIn(
                source="manual",
                source_ref=ref,
                calendar_id="manual",
                title=body.title,
                start_at=body.start,
                end_at=body.end,
                all_day=body.all_day,
            )
        except ValidationError:
            raise HTTPException(422, "invalid item") from None
        row = Event(user_id=1, updated_at=now, last_seen_at=now, **e.model_dump())
        db.add(row)
        db.commit()
        return {"id": f"event-{row.id}"}


@router.delete("/items/{item_id}")
def delete_item(item_id: str, request: Request):
    kind, _, num = item_id.partition("-")
    model = {"task": Task, "event": Event}.get(kind)
    with request.app.state.session_factory() as db:
        row = db.get(model, int(num)) if model and num.isdigit() else None
        if row is None or row.source != "manual":  # only items made here can be deleted here
            raise HTTPException(404, "not found")
        db.delete(row)
        db.commit()
    return {"deleted": item_id}


class GoalIn(BaseModel):
    text: str = Field(max_length=90)


def _day(request: Request, clock: Clock) -> str:
    tz = ZoneInfo(request.app.state.settings.user_timezone)
    return clock.now().astimezone(tz).date().isoformat()


@router.get("/goal/today")
def get_goal(request: Request, clock: Clock = Depends(get_clock)):
    day = _day(request, clock)
    with request.app.state.session_factory() as db:
        g = db.get(DailyGoal, day)
        return {"date": day, "text": g.text if g else None}


@router.put("/goal/today")
def put_goal(body: GoalIn, request: Request, clock: Clock = Depends(get_clock)):
    day = _day(request, clock)
    with request.app.state.session_factory() as db:
        db.merge(DailyGoal(day=day, text=body.text, updated_at=clock.now()))
        db.commit()
    return {"date": day, "text": body.text}


class Reminder(BaseModel):
    id: str
    title: str
    due: str | None = None
    completed: bool = False


class RemindersIn(BaseModel):
    reminders: list[Reminder]


@router.post("/ingest/reminders")
def ingest_reminders(body: RemindersIn, request: Request, clock: Clock = Depends(get_clock)):
    items = []
    for r in body.reminders:
        at, day = _due(r.due)
        try:
            items.append(
                TaskIn(
                    title=r.title,
                    scope="reminders",
                    source_ref=r.id,
                    due_at=at,
                    due_date=day,
                    done=r.completed,
                )
            )
        except ValidationError:
            raise HTTPException(422, "invalid reminder") from None
    with request.app.state.session_factory() as db:
        changed = sync_tasks(
            db,
            "reminders",
            "reminders",
            items,
            clock.now(),
            request.app.state.settings.user_timezone,
        )
    return {"received": len(items), "changed": changed}


class SnoozeIn(BaseModel):
    until: datetime


def _task(db, task_id: int) -> Task:
    t = db.get(Task, task_id)
    if t is None:
        raise HTTPException(404, "not found")
    return t


@router.post("/tasks/{task_id}/snooze")
def snooze(task_id: int, body: SnoozeIn, request: Request, clock: Clock = Depends(get_clock)):
    if body.until.tzinfo is None or body.until <= clock.now():
        raise HTTPException(422, "until must be timezone aware and in the future")
    with request.app.state.session_factory() as db:
        t = _task(db, task_id)
        t.snoozed_until, t.updated_at = body.until.astimezone(UTC), clock.now()
        db.commit()
    return {"id": task_id, "snoozed_until": body.until.astimezone(UTC).isoformat()}


@router.post("/tasks/{task_id}/done")
def done(task_id: int, request: Request, clock: Clock = Depends(get_clock)):
    with request.app.state.session_factory() as db:
        t = _task(db, task_id)
        t.status, t.locally_done, t.updated_at = "done", True, clock.now()
        db.commit()
    return {"id": task_id, "status": "done"}
