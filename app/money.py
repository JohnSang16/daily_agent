"""Money totals: spend vs income by month, spend by category, and what is held where.

Moves between my own accounts and credit card payments are not spending or income, and a
refund reduces spending instead of counting as income."""

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
