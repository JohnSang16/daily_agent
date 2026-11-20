"""Money endpoints: connect a bank, list accounts, list transactions. Read only."""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import and_, or_, select

from app.auth import require_token
from app.banks import display, store_item
from app.clock import Clock, get_clock
from app.crypto import TokenBox
from app.models import BankAccount, BankItem, Transaction
from app.money import CARD_PAYMENT, INTERNAL_PRIMARY, SPEND_TRANSFERS

router = APIRouter(dependencies=[Depends(require_token)])

DEMO = [
    ("Coffee Shop", "4.50", "out", "Food and drink"),
    ("Payroll", "+1200.00", "in", "Income"),
    ("Grocery Store", "62.18", "out", "Groceries"),
    ("Streaming", "11.99", "out", "Entertainment"),
]


def _plaid(request: Request):
    p = request.app.state.plaid
    if p is None:
        raise HTTPException(503, "bank connections are not configured")
    return p


def _box(request: Request) -> TokenBox:
    try:
        return TokenBox(request.app.state.settings.token_encryption_key)
    except RuntimeError:
        raise HTTPException(503, "token encryption key is not set") from None


@router.post("/banks/connect")
def connect(request: Request):
    return _plaid(request).link_token_create()


class CompleteIn(BaseModel):
    link_token: str


@router.post("/banks/connect/complete")
def connect_complete(body: CompleteIn, request: Request, clock: Clock = Depends(get_clock)):
    plaid, box = _plaid(request), _box(request)
    public = plaid.link_token_public_token(body.link_token)
    if public is None:
        raise HTTPException(409, "the bank screen is not finished yet")
    with request.app.state.session_factory() as db:
        try:
            item = store_item(db, box, plaid, public, clock.now())
        except ValueError as e:
            raise HTTPException(409, f"{e}. delete it first to reconnect it.") from None
        return {"id": item.id, "bank": item.institution_name}


@router.post("/banks/sandbox")
def sandbox(request: Request, clock: Clock = Depends(get_clock)):
    if request.app.state.settings.plaid_env != "sandbox":
        raise HTTPException(404, "not found")
    plaid, box = _plaid(request), _box(request)
    with request.app.state.session_factory() as db:
        item = store_item(db, box, plaid, plaid.sandbox_public_token(), clock.now())
        return {"id": item.id, "bank": item.institution_name}


@router.get("/banks")
def list_banks(request: Request):
    with request.app.state.session_factory() as db:
        items = {i.id: i for i in db.scalars(select(BankItem))}
        accts = db.scalars(select(BankAccount).order_by(BankAccount.id)).all()
        on = sum(a.enabled for a in accts)
        chip = "banks: all" if on == len(accts) else f"banks: {on} of {len(accts)}"
        return {
            "chip": chip,
            "items": [
                {
                    "id": i.id,
                    "bank": i.institution_name,
                    "last_sync_at": i.last_sync_at.isoformat() if i.last_sync_at else None,
                }
                for i in items.values()
            ],
            "accounts": [
                {
                    "id": a.id,
                    "item_id": a.item_id,
                    "bank": items[a.item_id].institution_name,
                    "nickname": a.nickname,
                    "mask": a.mask,
                    "enabled": a.enabled,
                    "kind": a.type or "other",
                    "subtype": a.subtype,
                    "balance_cents": a.balance_cents,
                }
                for a in accts
                if a.item_id in items
            ],
        }


class EnabledIn(BaseModel):
    enabled: bool


@router.patch("/banks/accounts/{account_id}")
def set_enabled(account_id: int, body: EnabledIn, request: Request):
    with request.app.state.session_factory() as db:
        a = db.get(BankAccount, account_id)
        if a is None:
            raise HTTPException(404, "not found")
        a.enabled = body.enabled
        db.commit()
    return {"id": account_id, "enabled": body.enabled}


@router.delete("/banks/{item_id}")
def delete_bank(item_id: int, request: Request):
    with request.app.state.session_factory() as db:
        item = db.get(BankItem, item_id)
        if item is None:
            raise HTTPException(404, "not found")
        remote = True
        try:  # disconnect my own link at the aggregator, local data goes either way
            _plaid(request).item_remove(_box(request).decrypt(item.access_token_enc))
        except Exception:
            remote = False
        ids = [a.id for a in db.scalars(select(BankAccount).where(BankAccount.item_id == item_id))]
        for t in db.scalars(select(Transaction).where(Transaction.account_id.in_(ids))):
            db.delete(t)
        for a in db.scalars(select(BankAccount).where(BankAccount.item_id == item_id)):
            db.delete(a)
        db.delete(item)
        db.commit()
    return {"deleted": item_id, "remote_removed": remote}


@router.get("/transactions")
def transactions(
    request: Request,
    bank: int | None = None,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    kind: Literal["all", "income", "spend"] = "all",
):
    with request.app.state.session_factory() as db:
        if db.scalars(select(BankItem.id)).first() is None:
            return {
                "demo": True,
                "note": "Demo data. Connect a bank to see yours.",
                "next_cursor": None,
                "transactions": [
                    {
                        "id": f"demo-{i}",
                        "date": date.today().isoformat(),
                        "merchant": m,
                        "amount": a,
                        "direction": d,
                        "bank": "Demo Bank",
                        "category": c,
                        "pending": False,
                    }
                    for i, (m, a, d, c) in enumerate(DEMO)
                ],
            }
        q = (
            select(Transaction, BankAccount, BankItem)
            .join(BankAccount, BankAccount.id == Transaction.account_id)
            .join(BankItem, BankItem.id == BankAccount.item_id)
            .where(BankAccount.enabled.is_(True))
        )
        if bank is not None:
            q = q.where(BankItem.id == bank)
        if kind == "income":  # paychecks and other real income, not transfers
            q = q.where(Transaction.direction == "in", Transaction.category == "INCOME")
        elif kind == "spend":  # leaves out moves between my accounts and card payments
            q = q.where(
                Transaction.direction == "out",
                or_(
                    Transaction.category.is_(None),
                    Transaction.category.not_in(INTERNAL_PRIMARY),
                    Transaction.category_detail.in_(SPEND_TRANSFERS),
                ),
                or_(
                    Transaction.category_detail.is_(None),
                    Transaction.category_detail != CARD_PAYMENT,
                ),
            )
        if cursor:
            try:
                d, _, i = cursor.rpartition(":")
                d, i = date.fromisoformat(d), int(i)
            except ValueError:
                raise HTTPException(422, "bad cursor") from None
            q = q.where(
                or_(
                    Transaction.posted_date < d,
                    and_(Transaction.posted_date == d, Transaction.id < i),
                )
            )
        rows = db.execute(
            q.order_by(Transaction.posted_date.desc(), Transaction.id.desc()).limit(limit + 1)
        ).all()
        more = len(rows) > limit
        rows = rows[:limit]
        out = [
            {
                "id": t.id,
                "date": t.posted_date.isoformat(),
                "merchant": t.merchant,
                "amount": display(t.amount_cents, t.direction),
                "direction": t.direction,
                "bank": it.institution_name,
                "category": t.category,
                "pending": t.pending,
            }
            for t, a, it in rows
        ]
        nxt = f"{rows[-1][0].posted_date.isoformat()}:{rows[-1][0].id}" if more else None
        return {"demo": False, "note": None, "next_cursor": nxt, "transactions": out}
