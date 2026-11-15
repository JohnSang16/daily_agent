from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


def _aware(v: datetime | None) -> datetime | None:
    if v is not None and v.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return v


class TaskIn(BaseModel):
    """What a source produces. Date-only dues arrive as `due_date` and are converted on upsert."""

    title: str
    scope: str
    source_ref: str
    due_at: datetime | None = None
    due_date: date | None = None
    effort_minutes: int | None = None
    importance: int | None = None
    done: bool = False
    needs_review: bool = False
    review_reason: str | None = None

    @field_validator("title")
    @classmethod
    def _title(cls, v):
        if not v.strip():
            raise ValueError("title must not be empty")
        return v.strip()

    @field_validator("due_at")
    @classmethod
    def _due_aware(cls, v):
        return _aware(v)

    @field_validator("importance")
    @classmethod
    def _imp(cls, v):
        if v is not None and not 1 <= v <= 5:
            raise ValueError("importance must be 1 to 5")
        return v

    @model_validator(mode="after")
    def _one_due(self):
        if self.due_at is not None and self.due_date is not None:
            raise ValueError("give due_at or due_date, not both")
        return self


class EventIn(BaseModel):
    source: Literal["google_calendar", "outlook", "manual"]
    source_ref: str
    calendar_id: str
    title: str
    start_at: datetime
    end_at: datetime
    all_day: bool = False
    busy: bool = True
    status: Literal["confirmed", "tentative", "cancelled"] = "confirmed"
    location: str | None = None

    @field_validator("title")
    @classmethod
    def _title(cls, v):
        if not v.strip():
            raise ValueError("title must not be empty")
        return v.strip()

    @field_validator("start_at", "end_at")
    @classmethod
    def _tz(cls, v):
        return _aware(v)

    @model_validator(mode="after")
    def _order(self):
        if self.end_at < self.start_at:
            raise ValueError("end_at is before start_at")
        return self


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    title: str
    due_at: datetime | None
    due_is_date_only: bool
    effort_minutes: int | None
    importance: int | None
    status: str
    needs_review: bool


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str
    start_at: datetime
    end_at: datetime
    all_day: bool
