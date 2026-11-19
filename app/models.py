from datetime import UTC, date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Index,
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
    locally_done: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
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


class DailyGoal(Base):
    __tablename__ = "daily_goal"

    day: Mapped[str] = mapped_column(String, primary_key=True)  # YYYY-MM-DD in my time zone
    text: Mapped[str] = mapped_column(String)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime)


class NoteChunk(Base):
    __tablename__ = "note_chunks"
    __table_args__ = (UniqueConstraint("path", "chunk_index"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    path: Mapped[str] = mapped_column(String, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    heading: Mapped[str] = mapped_column(String, default="")
    content_hash: Mapped[str] = mapped_column(String)
    text: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime)


class BankItem(Base):
    """One bank login at the aggregator. The access token is only ever stored encrypted."""

    __tablename__ = "bank_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, default=1)
    plaid_item_id: Mapped[str] = mapped_column(String)
    institution_id: Mapped[str] = mapped_column(String, default="")
    institution_name: Mapped[str] = mapped_column(String, default="")
    access_token_enc: Mapped[str] = mapped_column(Text)
    cursor: Mapped[str | None] = mapped_column(String, nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)


class BankAccount(Base):
    __tablename__ = "bank_accounts"
    __table_args__ = (UniqueConstraint("item_id", "account_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(Integer, index=True)
    account_id: Mapped[str] = mapped_column(String)
    nickname: Mapped[str] = mapped_column(String, default="")
    mask: Mapped[str] = mapped_column(String, default="")  # last four digits only
    type: Mapped[str] = mapped_column(String, default="")  # depository, credit, loan, investment
    subtype: Mapped[str] = mapped_column(String, default="")  # checking, savings, brokerage ...
    balance_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (Index("ix_transactions_date_id", "posted_date", "id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(Integer, index=True)  # bank_accounts.id
    source_id: Mapped[str] = mapped_column(String, unique=True)
    posted_date: Mapped[date] = mapped_column(Date)
    merchant: Mapped[str] = mapped_column(Text)
    amount_cents: Mapped[int] = mapped_column(Integer)  # always positive, see direction
    direction: Mapped[str] = mapped_column(String)  # in, out
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    category_detail: Mapped[str | None] = mapped_column(String, nullable=True)
    pending: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime)


class Budget(Base):
    """A monthly spending goal. category is a Plaid category, or TOTAL for all spending."""

    __tablename__ = "budgets"

    category: Mapped[str] = mapped_column(String, primary_key=True)
    limit_cents: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime)
