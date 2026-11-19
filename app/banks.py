"""Bank data: store a connection, sync transactions, display amounts. Read only, local storage."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crypto import TokenBox
from app.models import BankAccount, BankItem, Transaction


def cents(amount) -> int:
    return int((Decimal(str(abs(amount))) * 100).to_integral_value())


def signed_cents(amount) -> int:
    return int((Decimal(str(amount)) * 100).to_integral_value())


def display(amount_cents: int, direction: str) -> str:
    s = f"{amount_cents // 100}.{amount_cents % 100:02d}"
    return "+" + s if direction == "in" else s


def _upsert_accounts(db: Session, item: BankItem, accounts: list[dict]) -> dict[str, int]:
    have = {
        a.account_id: a
        for a in db.scalars(select(BankAccount).where(BankAccount.item_id == item.id))
    }
    for a in accounts:
        row = have.get(a["account_id"])
        if row is None:
            row = BankAccount(item_id=item.id, account_id=a["account_id"], enabled=True)
            db.add(row)
            have[a["account_id"]] = row
        row.nickname, row.mask = a.get("name") or "", a.get("mask") or ""
        row.type, row.subtype = a.get("type") or "", a.get("subtype") or ""
        current = (a.get("balances") or {}).get("current")
        row.balance_cents = signed_cents(current) if current is not None else None
    db.flush()
    return {k: v.id for k, v in have.items()}


def store_item(db: Session, box: TokenBox, plaid, public_token: str, now: datetime) -> BankItem:
    access, plaid_item = plaid.exchange(public_token)
    inst_id, inst_name, accounts = plaid.accounts(access)
    item = BankItem(
        user_id=1,
        plaid_item_id=plaid_item,
        institution_id=inst_id,
        institution_name=inst_name,
        access_token_enc=box.encrypt(access),
        created_at=now,
    )
    db.add(item)
    db.flush()
    _upsert_accounts(db, item, accounts)
    db.commit()
    return item


def _by_source_id(db: Session, source_id: str) -> Transaction | None:
    return db.scalars(select(Transaction).where(Transaction.source_id == source_id)).first()


def _apply(db: Session, acct_ids: dict[str, int], res: dict, now: datetime) -> int:
    changed = 0
    for t in res.get("added", []) + res.get("modified", []):
        acct = acct_ids.get(t["account_id"])
        if acct is None:
            continue
        row = _by_source_id(db, t["transaction_id"])
        if row is None and t.get("pending_transaction_id"):  # the pending one just posted
            row = _by_source_id(db, t["pending_transaction_id"])
        if row is None:
            row = Transaction(account_id=acct)
            db.add(row)
        row.source_id, row.account_id = t["transaction_id"], acct
        row.posted_date = date.fromisoformat(t["date"])
        row.merchant = t.get("merchant_name") or t.get("name") or "Unknown"
        row.amount_cents = cents(t["amount"])
        row.direction = "in" if Decimal(str(t["amount"])) < 0 else "out"
        pfc = t.get("personal_finance_category") or {}
        row.category, row.category_detail = pfc.get("primary"), pfc.get("detailed")
        row.pending, row.updated_at = bool(t.get("pending")), now
        db.flush()
        changed += 1
    for r in res.get("removed", []):
        if row := _by_source_id(db, r["transaction_id"]):
            db.delete(row)
            changed += 1
    return changed


def sync_banks(db: Session, box: TokenBox, plaid, now: datetime) -> int:
    changed = 0
    for item in db.scalars(select(BankItem)).all():
        access = box.decrypt(item.access_token_enc)
        _, _, accounts = plaid.accounts(access)
        acct_ids = _upsert_accounts(db, item, accounts)
        db.commit()  # release the write lock before the next outbound call's own audit write
        while True:
            res = plaid.transactions_sync(access, item.cursor)
            changed += _apply(db, acct_ids, res, now)
            item.cursor = res["next_cursor"]
            db.commit()
            if not res.get("has_more"):
                break
        item.last_sync_at = now
        db.commit()
    return changed
