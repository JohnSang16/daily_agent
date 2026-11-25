"""Load John's money goals and budgets (set 2026-11-25) into the agent's database.

Run on the host Mac after `alembic upgrade head`: `uv run python -m scripts.seed_money_goals`.
Safe to rerun, it replaces the same ids. Accounts are found by their last four digits."""

from datetime import UTC, date, datetime

from sqlalchemy import select

from app.config import Settings
from app.db import make_session_factory
from app.models import BankAccount, Budget, SavingsGoal

END_2026, SPRING, SUMMER = date(2026, 12, 31), date(2027, 5, 31), date(2027, 8, 31)
EMERGENCY, JAPAN, ROTH, BROKERAGE = "2881", "6840", "8039", "5024"

# (id, name, kind, account mask or None, target dollars, due)
GOALS = [
    ("2026-1-emergency", "emergency", "account", EMERGENCY, 1_500, END_2026),
    ("2026-2-japan", "japan", "account", JAPAN, 900, END_2026),
    ("2026-3-roth", "roth", "account", ROTH, 1_614, END_2026),
    ("2026-5-cards", "credit cards", "cards_owed", None, 0, END_2026),
    ("2026-6-net", "net worth", "net_worth", None, 4_000, END_2026),
    ("spring-1-emergency", "emergency", "account", EMERGENCY, 2_000, SPRING),
    ("spring-2-japan", "japan", "account", JAPAN, 3_000, SPRING),
    ("spring-3-roth", "roth", "account", ROTH, 3_714, SPRING),
    ("spring-5-cards", "credit cards", "cards_owed", None, 0, SPRING),
    ("spring-6-net", "net worth", "net_worth", None, 8_000, SPRING),
    ("summer-1-emergency", "emergency", "account", EMERGENCY, 3_000, SUMMER),
    ("summer-3-roth", "roth", "account", ROTH, 11_214, SUMMER),
    ("summer-4-brokerage", "brokerage", "account", BROKERAGE, 6_000, SUMMER),
    ("summer-5-cards", "credit cards", "cards_owed", None, 0, SUMMER),
    ("summer-6-net", "net worth", "net_worth", None, 22_000, SUMMER),
]
BUDGETS = {"FOOD_AND_DRINK": 205, "TRANSPORTATION": 120, "GENERAL_MERCHANDISE": 60}


def main() -> None:
    factory = make_session_factory(Settings().database_url)
    with factory() as db:

        def account(mask: str) -> int:
            a = db.scalars(
                select(BankAccount).where(BankAccount.mask == mask).order_by(BankAccount.id)
            ).first()
            if a is None:
                raise SystemExit(f"no account ending in {mask}, connect it first")
            return a.id

        db.merge(
            SavingsGoal(
                id="stretch",
                name="stretch",
                kind="income_since",
                account_id=None,
                target_cents=606_000_00,
                start=date(2026, 11, 25),
                due=date(2027, 11, 25),
                floor_cents=100_000_00,
            )
        )
        for gid, name, kind, mask, dollars, due in GOALS:
            db.merge(
                SavingsGoal(
                    id=gid,
                    name=name,
                    kind=kind,
                    account_id=account(mask) if mask else None,
                    target_cents=dollars * 100,
                    start=None,
                    due=due,
                    floor_cents=None,
                )
            )
        for cat, dollars in BUDGETS.items():
            db.merge(Budget(category=cat, limit_cents=dollars * 100, updated_at=datetime.now(UTC)))
        db.commit()
    print(f"loaded 1 stretch goal, {len(GOALS)} goals, {len(BUDGETS)} budgets")


if __name__ == "__main__":
    main()
