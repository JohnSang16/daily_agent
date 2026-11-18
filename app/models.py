from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class UTCDateTime(TypeDecorator):
    """Stored as naive UTC (portable across SQLite and Postgres), returned timezone-aware."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime: store UTC-aware values only")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        return None if value is None else value.replace(tzinfo=UTC)


class OutboundCall(Base):
    """Audit row: method, host, path template only. Never bodies or query strings."""

    __tablename__ = "outbound_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, default=1)
    ts: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    integration: Mapped[str] = mapped_column(String)
    method: Mapped[str] = mapped_column(String)
    host: Mapped[str] = mapped_column(String)
    path_template: Mapped[str] = mapped_column(String)
    allowed: Mapped[bool] = mapped_column(Boolean)
    status: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (UniqueConstraint("user_id", "source", "fingerprint"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, default=1)
    source: Mapped[str] = mapped_column(String)  # obsidian, gmail_digest, reminders, manual
    scope: Mapped[str] = mapped_column(String)  # file path or message id (deviation: see log)
    source_ref: Mapped[str] = mapped_column(String)
    fingerprint: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(Text)
    due_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    due_is_date_only: Mapped[bool] = mapped_column(Boolean, default=False)
    effort_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    importance: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String, default="open")  # open, done, gone
    snoozed_until: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime)


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("user_id", "source", "calendar_id", "source_ref", "start_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, default=1)
    source: Mapped[str] = mapped_column(String)  # google_calendar, outlook, manual
    source_ref: Mapped[str] = mapped_column(String)
    calendar_id: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(Text)
    start_at: Mapped[datetime] = mapped_column(UTCDateTime)
    end_at: Mapped[datetime] = mapped_column(UTCDateTime)
    all_day: Mapped[bool] = mapped_column(Boolean, default=False)
    busy: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String, default="confirmed")
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime)


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    status: Mapped[str] = mapped_column(String)  # ok, error, partial
    items_seen: Mapped[int] = mapped_column(Integer, default=0)
    items_changed: Mapped[int] = mapped_column(Integer, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class OAuthToken(Base):
    __tablename__ = "oauth_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, default=1)
    provider: Mapped[str] = mapped_column(String)
    encrypted_blob: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime)


class LlmUsage(Base):
    __tablename__ = "llm_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[datetime] = mapped_column(UTCDateTime)
    purpose: Mapped[str] = mapped_column(String)  # extraction, explanation
    model: Mapped[str] = mapped_column(String)
    input_tokens: Mapped[int] = mapped_column(Integer)
    output_tokens: Mapped[int] = mapped_column(Integer)


class ExplanationCache(Base):
    __tablename__ = "explanation_cache"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
