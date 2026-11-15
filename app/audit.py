import logging
from datetime import timedelta
from typing import Protocol

from app.clock import Clock
from app.models import OutboundCall

log = logging.getLogger("audit")


class AuditSink(Protocol):
    def record(
        self,
        integration: str,
        method: str,
        host: str,
        path_template: str,
        allowed: bool,
        status: int | None = None,
    ) -> None: ...


class DbAudit:
    def __init__(self, session_factory, clock: Clock):
        self.sf, self.clock = session_factory, clock

    def record(self, integration, method, host, path_template, allowed, status=None):
        ts = self.clock.now().replace(tzinfo=None)
        with self.sf() as s:
            s.add(
                OutboundCall(
                    ts=ts,
                    integration=integration,
                    method=method,
                    host=host,
                    path_template=path_template,
                    allowed=allowed,
                    status=status,
                )
            )
            s.commit()
        if not allowed:
            log.warning("DENIED %s %s %s (%s)", method, host, path_template, integration)


def summarize(session_factory, clock: Clock, days: int = 7) -> dict:
    since = (clock.now() - timedelta(days=days)).replace(tzinfo=None)
    with session_factory() as s:
        rows = (
            s.query(OutboundCall).filter(OutboundCall.ts >= since).order_by(OutboundCall.ts).all()
        )
    by: dict[str, dict[str, int]] = {}
    for r in rows:
        c = by.setdefault(r.integration, {"allowed": 0, "denied": 0})
        c["allowed" if r.allowed else "denied"] += 1
    denials = [
        {
            "ts": r.ts.isoformat(),
            "integration": r.integration,
            "method": r.method,
            "host": r.host,
            "path": r.path_template,
        }
        for r in rows
        if not r.allowed
    ]
    return {"days": days, "by_integration": by, "denials": denials, "warning": bool(denials)}
