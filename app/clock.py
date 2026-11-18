from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock:
    def __init__(self, at: datetime):
        self._at = at

    def now(self) -> datetime:
        return self._at


def get_clock() -> Clock:
    return SystemClock()
