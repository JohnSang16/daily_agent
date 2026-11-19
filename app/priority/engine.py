"""Pure priority engine: no database, no network, no clock. Everything arrives as arguments."""

from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from itertools import accumulate
from zoneinfo import ZoneInfo

Block = tuple[datetime, datetime]


@dataclass(frozen=True)
class Config:
    user_timezone: str = "America/New_York"
    work_start: time = time(9)
    work_end: time = time(17)
    default_effort_minutes: int = 60
    horizon_days: int = 14
    min_block_minutes: int = 15
    stale_overdue_days: int = 14  # older overdue items drop out of the ranking, 0 keeps them


@dataclass
class TaskView:
    id: int
    due_at: datetime | None
    effort_minutes: int | None
    importance: int | None
    created_at: datetime
    status: str = "open"
    snoozed_until: datetime | None = None
    needs_review: bool = False


@dataclass
class EventView:
    start_at: datetime
    end_at: datetime
    busy: bool = True
    status: str = "confirmed"


@dataclass(frozen=True)
class RankedItem:
    task_id: int
    rank: int
    reasons: list[str]
    at_risk: bool
    free_minutes_before_due: int | None
    cumulative_effort_minutes: int | None


@dataclass(frozen=True)
class RankingResult:
    ranked: list[RankedItem]
    top_task_id: int | None
    free_blocks_today: list[Block]
    suggested_block: Block | None = None
    stale_ids: list[int] = field(default_factory=list)  # overdue too long to rank
    _blocks: list[Block] = field(default_factory=list, repr=False, compare=False)


def _free_blocks(events, now: datetime, cfg: Config) -> list[Block]:
    """Working windows from now through the horizon, minus merged busy events, minus slivers."""
    tz = ZoneInfo(cfg.user_timezone)
    today = now.astimezone(tz).date()
    busy = sorted((e.start_at, e.end_at) for e in events if e.busy and e.status != "cancelled")
    merged: list[list[datetime]] = []
    for s, e in busy:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    out: list[Block] = []
    for i in range(cfg.horizon_days + 1):
        d = today + timedelta(days=i)
        start = max(datetime.combine(d, cfg.work_start, tz).astimezone(UTC), now)
        end = datetime.combine(d, cfg.work_end, tz).astimezone(UTC)
        cur = start
        for bs, be in merged:
            if be <= cur or bs >= end:
                continue
            if bs > cur:
                out.append((cur, bs))
            cur = max(cur, be)
        if cur < end:
            out.append((cur, end))
    min_td = timedelta(minutes=cfg.min_block_minutes)
    return [b for b in out if b[1] - b[0] >= min_td]


def _reasons(due, now, today: date, tz, effort_missing, needs_review) -> list[str]:
    r: list[str] = []
    if due is None:
        r.append("NO_DUE_DATE")
    elif due < now:
        r.append("OVERDUE")
    else:
        delta = (due.astimezone(tz).date() - today).days
        if delta == 0:
            r.append("DUE_TODAY")
        elif delta == 1:
            r.append("DUE_TOMORROW")
        elif delta <= 7:
            r.append("DUE_THIS_WEEK")
    if needs_review:
        r.append("NEEDS_REVIEW")
    if effort_missing:
        r.append("DEFAULT_EFFORT_USED")
    return r


def rank(tasks, events, now: datetime, cfg: Config) -> RankingResult:
    tz = ZoneInfo(cfg.user_timezone)
    today = now.astimezone(tz).date()
    imp = lambda t: t.importance or 3  # noqa: E731
    eff = lambda t: t.effort_minutes or cfg.default_effort_minutes  # noqa: E731

    live = [
        t for t in tasks if t.status == "open" and not (t.snoozed_until and t.snoozed_until > now)
    ]
    stale_ids: list[int] = []
    if cfg.stale_overdue_days > 0:
        cutoff = now - timedelta(days=cfg.stale_overdue_days)
        stale_ids = [t.id for t in live if t.due_at and t.due_at < cutoff]
        live = [t for t in live if t.id not in stale_ids]
    dated = sorted(
        (t for t in live if t.due_at),
        key=lambda t: (t.due_at, -imp(t), eff(t), t.created_at, t.id),
    )
    undated = sorted((t for t in live if not t.due_at), key=lambda t: (-imp(t), t.created_at, t.id))

    blocks = _free_blocks(events, now, cfg)
    ends = [b[1] for b in blocks]
    cum_minutes = list(
        accumulate((int((e - s).total_seconds() // 60) for s, e in blocks), initial=0)
    )

    def free_before(due: datetime) -> int:
        i = bisect_right([b[0] for b in blocks], due)  # blocks starting at or before due
        if i == 0:
            return 0
        total = cum_minutes[i]
        if ends[i - 1] > due:  # last block is cut off by the due moment
            total -= int((ends[i - 1] - due).total_seconds() // 60)
        return total

    items: list[RankedItem] = []
    running = 0
    for n, t in enumerate(dated):
        running += eff(t)
        free = free_before(t.due_at)
        reasons = _reasons(t.due_at, now, today, tz, t.effort_minutes is None, t.needs_review)
        nxt = dated[n + 1] if n + 1 < len(dated) else None
        if nxt and nxt.due_at == t.due_at:
            if imp(t) != imp(nxt):
                reasons.append("TIE_BROKEN_BY_IMPORTANCE")
            elif eff(t) != eff(nxt):
                reasons.append("TIE_BROKEN_BY_EFFORT")
        at_risk = t.due_at < now or running > free
        if at_risk:
            reasons.append("AT_RISK")
        items.append(RankedItem(t.id, n + 1, reasons, at_risk, free, running))
    for t in undated:
        reasons = _reasons(None, now, today, tz, t.effort_minutes is None, t.needs_review)
        items.append(RankedItem(t.id, len(items) + 1, reasons, False, None, None))

    today_blocks = [b for b in blocks if b[0].astimezone(tz).date() == today]
    top = (dated + undated)[0] if items else None
    suggested = None
    if top:
        need = timedelta(minutes=eff(top))
        suggested = next((b for b in today_blocks if b[1] - b[0] >= need), None)
    return RankingResult(
        items, top.id if top else None, today_blocks, suggested, stale_ids=stale_ids
    )
