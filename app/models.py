from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class OutboundCall(Base):
    """Audit row: method, host, path template only. Never bodies or query strings."""

    __tablename__ = "outbound_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, default="me")
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)  # naive UTC
    integration: Mapped[str] = mapped_column(String)
    method: Mapped[str] = mapped_column(String)
    host: Mapped[str] = mapped_column(String)
    path_template: Mapped[str] = mapped_column(String)
    allowed: Mapped[bool] = mapped_column(Boolean)
    status: Mapped[int | None] = mapped_column(Integer, nullable=True)
