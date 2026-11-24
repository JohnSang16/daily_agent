"""Money totals: spend vs income by month, spend by category, and what is held where.

Moves between my own accounts and credit card payments are not spending or income, and a
refund reduces spending instead of counting as income."""

from calendar import monthrange
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BankAccount, Transaction

INTERNAL_PRIMARY = {"TRANSFER_IN", "TRANSFER_OUT"}
CARD_PAYMENT = "LOAN_PAYMENTS_CREDIT_CARD_PAYMENT"
# transfer details that are real spending, not a move between my own accounts
SPEND_TRANSFERS = {"TRANSFER_OUT_WITHDRAWAL"}  # ATM and teller cash
SAVINGS_SUBTYPES = {"savings", "cd", "money market", "hsa", "cash management"}


def is_internal(category: str | None, detail: str | None) -> bool:
    if detail == CARD_PAYMENT:
        return True
    return category in INTERNAL_PRIMARY and detail not in SPEND_TRANSFERS


def month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def last_months(today: date, n: int) -> list[str]:
    y, m, out = today.year, today.month, []
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    return out[::-1]


def month_totals(db: Session, months: list[str]) -> tuple[dict, dict]:
    """({month: {income_cents, spend_cents}}, {category: net spend cents in the newest month})."""
    first = date(int(months[0][:4]), int(months[0][5:]), 1)
    rows = db.execute(
        select(
            Transaction.posted_date,
            Transaction.direction,
            Transaction.amount_cents,
            Transaction.category,
            Transaction.category_detail,
        )
        .join(BankAccount, BankAccount.id == Transaction.account_id)
        .where(BankAccount.enabled.is_(True), Transaction.posted_date >= first)
    ).all()
    out = {m: {"income": 0, "spend": 0} for m in months}
    cats: dict[str, int] = {}
    for d, direction, cents, cat, detail in rows:
        m = month_key(d)
        if m not in out or is_internal(cat, detail):
            continue
        if direction == "in" and cat == "INCOME":
            out[m]["income"] += cents
            continue
        signed = cents if direction == "out" else -cents  # a refund takes spending back
        out[m]["spend"] += signed
        if m == months[-1]:
            cats[cat or "OTHER"] = cats.get(cat or "OTHER", 0) + signed
    for v in out.values():
        v["spend"] = max(v["spend"], 0)
    return out, {k: v for k, v in cats.items() if v > 0}


def daily_cumulative_spend(db: Session, today: date, start: date | None = None) -> list[tuple[date, int]]:
    """One point per day from `start` (day 1 of the current month if omitted) through today: a
    running total of spend cents, same filtering rules as month_totals (is_internal, refunds
    reduce spend). A day with nothing to add carries the prior day's total forward, so the series
    has no gaps. The running sum is floored at 0 the same way month_totals floors the month total:
    by clamping the cumulative sum at each point, not by clamping (and losing) any single day's
    delta. Pass `start` for a rolling window (the app's 7D/1M chart) instead of a calendar month."""
    if start is None:
        start = date(today.year, today.month, 1)
    rows = db.execute(
        select(
            Transaction.posted_date,
            Transaction.direction,
            Transaction.amount_cents,
            Transaction.category,
            Transaction.category_detail,
        )
        .join(BankAccount, BankAccount.id == Transaction.account_id)
        .where(
            BankAccount.enabled.is_(True),
            Transaction.posted_date >= start,
            Transaction.posted_date <= today,
        )
    ).all()
    by_day: dict[date, int] = {}
    for d, direction, cents, cat, detail in rows:
        if is_internal(cat, detail) or (direction == "in" and cat == "INCOME"):
            continue
        signed = cents if direction == "out" else -cents
        by_day[d] = by_day.get(d, 0) + signed
    out: list[tuple[date, int]] = []
    raw = 0
    for i in range((today - start).days + 1):
        d = date.fromordinal(start.toordinal() + i)
        raw += by_day.get(d, 0)
        out.append((d, max(raw, 0)))
    return out


def category_spend(db: Session, today: date, start: date) -> dict[str, int]:
    """Net spend by category between start and today, same filtering as month_totals: internal
    transfers and income are excluded, a refund reduces its own category instead of counting
    separately. For the app's category donut to follow the trend chart's range picker instead of
    always reading the current calendar month."""
    rows = db.execute(
        select(Transaction.direction, Transaction.amount_cents, Transaction.category, Transaction.category_detail)
        .join(BankAccount, BankAccount.id == Transaction.account_id)
        .where(
            BankAccount.enabled.is_(True),
            Transaction.posted_date >= start,
            Transaction.posted_date <= today,
        )
    ).all()
    cats: dict[str, int] = {}
    for direction, cents, cat, detail in rows:
        if is_internal(cat, detail) or (direction == "in" and cat == "INCOME"):
            continue
        signed = cents if direction == "out" else -cents
        cats[cat or "OTHER"] = cats.get(cat or "OTHER", 0) + signed
    return {k: v for k, v in cats.items() if v > 0}


def _next_month(d: date) -> date:
    y, m = (d.year, d.month + 1) if d.month < 12 else (d.year + 1, 1)
    return date(y, m, min(d.day, monthrange(y, m)[1]))


def recurring(db: Session, today: date, lookback_days: int = 100) -> list[dict]:
    """Bills and subscriptions: a merchant charged in 2 or more months of the lookback window,
    about once a month, every charge within 20 percent of the middle amount. Transfers, card
    payments and income never count. Soonest expected charge first."""
    # ponytail: monthly bills only, next_date is last charge + 1 month; weekly or yearly need gaps
    since = date.fromordinal(today.toordinal() - lookback_days)
    rows = db.execute(
        select(
            Transaction.posted_date,
            Transaction.merchant,
            Transaction.amount_cents,
            Transaction.category,
            Transaction.category_detail,
        )
        .join(BankAccount, BankAccount.id == Transaction.account_id)
        .where(
            BankAccount.enabled.is_(True),
            Transaction.direction == "out",
            Transaction.pending.is_(False),
            Transaction.posted_date >= since,
            Transaction.posted_date <= today,
        )
        .order_by(Transaction.posted_date)
    ).all()
    groups: dict[str, list] = {}
    for r in rows:
        if not is_internal(r.category, r.category_detail):
            groups.setdefault(r.merchant.strip().lower(), []).append(r)
    out = []
    for charges in groups.values():
        months = {month_key(r.posted_date) for r in charges}
        if len(months) < 2 or len(charges) > len(months) + 1:
            continue
        amounts = sorted(r.amount_cents for r in charges)
        mid = amounts[len(amounts) // 2]
        if any(abs(a - mid) > mid * 0.2 for a in amounts):
            continue
        last = charges[-1]
        out.append(
            {
                "merchant": last.merchant,
                "amount_cents": last.amount_cents,
                "category": last.category,
                "last_date": last.posted_date.isoformat(),
                "next_date": _next_month(last.posted_date).isoformat(),
                "paid_this_month": month_key(last.posted_date) == month_key(today),
            }
        )
    return sorted(out, key=lambda i: (i["next_date"], i["merchant"]))


def holdings(db: Session) -> dict:
    """Where the money sits, from the latest balance of every enabled account."""
    h = {"cash": 0, "savings": 0, "invested": 0, "credit_owed": 0, "loans_owed": 0}
    for a in db.scalars(select(BankAccount).where(BankAccount.enabled.is_(True))):
        b = a.balance_cents or 0
        if a.type == "investment":
            h["invested"] += b
        elif a.type == "credit":
            h["credit_owed"] += b
        elif a.type == "loan":
            h["loans_owed"] += b
        elif a.subtype in SAVINGS_SUBTYPES:
            h["savings"] += b
        elif a.type == "depository":
            h["cash"] += b
    net = h["cash"] + h["savings"] + h["invested"] - h["credit_owed"] - h["loans_owed"]
    return {f"{k}_cents": v for k, v in h.items()} | {"net_cents": net}
