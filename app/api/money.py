"""Money overview: spend vs income, categories, holdings, budget goals, and savings goals."""

from datetime import date, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.auth import require_token
from app.clock import Clock, get_clock
from app.models import BankAccount, Budget, SavingsGoal
from app.money import (
    category_spend,
    daily_cumulative_spend,
    holdings,
    income_since,
    last_months,
    month_totals,
    recurring,
)

router = APIRouter(dependencies=[Depends(require_token)])


def _today(request: Request, clock: Clock) -> date:
    return clock.now().astimezone(ZoneInfo(request.app.state.settings.user_timezone)).date()


@router.get("/money/summary")
def summary(
    request: Request,
    months: int = Query(6, ge=1, le=24),
    daily_days: int | None = Query(None, ge=1, le=400),
    category_days: int | None = Query(None, ge=1, le=20000),
    clock: Clock = Depends(get_clock),
):
    today = _today(request, clock)
    keys = last_months(today, months)
    daily_start = today - timedelta(days=daily_days - 1) if daily_days else None
    with request.app.state.session_factory() as db:
        totals, cats = month_totals(db, keys)
        now = totals[keys[-1]]
        # category_days follows the app's range picker (7D/1M/3M/1Y/ALL); without it, the
        # category donut always falls back to just the current calendar month
        if category_days:
            cats = category_spend(db, today, today - timedelta(days=category_days - 1))
        return {
            "months": [
                {"month": m, "income_cents": totals[m]["income"], "spend_cents": totals[m]["spend"]}
                for m in keys
            ],
            "this_month": {
                "month": keys[-1],
                "income_cents": now["income"],
                "spend_cents": now["spend"],
                "net_cents": now["income"] - now["spend"],
            },
            "categories": [
                {"category": c, "spend_cents": v}
                for c, v in sorted(cats.items(), key=lambda kv: (-kv[1], kv[0]))[:8]
            ],
            "holdings": holdings(db),
            "daily": [
                {"date": d.isoformat(), "cumulative_spend_cents": cents}
                for d, cents in daily_cumulative_spend(db, today, daily_start)
            ],
        }


@router.get("/money/recurring")
def recurring_charges(request: Request, clock: Clock = Depends(get_clock)):
    with request.app.state.session_factory() as db:
        items = recurring(db, _today(request, clock))
    return {"items": items, "monthly_cents": sum(i["amount_cents"] for i in items)}


class BudgetIn(BaseModel):
    limit_cents: int = Field(gt=0, le=100_000_000)


CATEGORY = Path(pattern=r"^[A-Z_]{2,40}$")


@router.get("/budgets")
def list_budgets(request: Request, clock: Clock = Depends(get_clock)):
    today = _today(request, clock)
    tz = ZoneInfo(request.app.state.settings.user_timezone)
    with request.app.state.session_factory() as db:
        rows = db.scalars(select(Budget)).all()

        # spend tracked since the budget was set (updated_at), not the whole calendar month: a
        # budget you just created reads $0 spent right away, not the month's pre-existing total
        def spent(b: Budget) -> int:
            start = b.updated_at.astimezone(tz).date()
            cats = category_spend(db, today, start)
            return sum(cats.values()) if b.category == "TOTAL" else cats.get(b.category, 0)

        out = [
            {"category": b.category, "limit_cents": b.limit_cents, "spent_cents": spent(b)}
            for b in rows
        ]
    return sorted(out, key=lambda x: (x["category"] != "TOTAL", x["category"]))


@router.put("/budgets/{category}")
def set_budget(
    category: str = CATEGORY,
    body: BudgetIn = ...,
    request: Request = ...,
    clock: Clock = Depends(get_clock),
):
    with request.app.state.session_factory() as db:
        db.merge(Budget(category=category, limit_cents=body.limit_cents, updated_at=clock.now()))
        db.commit()
    return {"category": category, "limit_cents": body.limit_cents}


@router.delete("/budgets/{category}")
def delete_budget(request: Request, category: str = CATEGORY):
    with request.app.state.session_factory() as db:
        b = db.get(Budget, category)
        if b is None:
            raise HTTPException(404, "not found")
        db.delete(b)
        db.commit()
    return {"deleted": category}


class GoalIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    kind: Literal["account", "net_worth", "invested", "cards_owed", "income_since"]
    account_id: int | None = None
    target_cents: int = Field(ge=0, le=10_000_000_000)
    start: date | None = None
    due: date
    floor_cents: int | None = Field(None, gt=0)


GOAL_ID = Path(pattern=r"^[a-z0-9_-]{1,40}$")


def _goal_out(g: SavingsGoal, h: dict, db) -> dict:
    if g.kind == "account":
        a = db.get(BankAccount, g.account_id)
        cur = (a.balance_cents or 0) if a and a.enabled else 0
    elif g.kind == "income_since":
        cur = income_since(db, g.start)
    else:
        cur = h[
            {
                "net_worth": "net_cents",
                "invested": "invested_cents",
                "cards_owed": "credit_owed_cents",
            }[g.kind]
        ]
    met = cur <= g.target_cents if g.kind == "cards_owed" else cur >= g.target_cents
    frac = (
        (1.0 if met else 0.0) if g.kind == "cards_owed" else min(max(cur, 0) / g.target_cents, 1.0)
    )
    return {
        "id": g.id,
        "name": g.name,
        "kind": g.kind,
        "account_id": g.account_id,
        "target_cents": g.target_cents,
        "current_cents": cur,
        "fraction": round(frac, 4),
        "met": met,
        "start": g.start.isoformat() if g.start else None,
        "due": g.due.isoformat(),
        "floor_cents": g.floor_cents,
    }


@router.get("/money/goals")
def list_goals(request: Request):
    with request.app.state.session_factory() as db:
        h = holdings(db)
        rows = db.scalars(select(SavingsGoal).order_by(SavingsGoal.due, SavingsGoal.id)).all()
        out = [_goal_out(g, h, db) for g in rows]
    # the stretch card is identified by its reserved id, not its kind: kind only decides how a
    # goal's current value is computed, and is not exclusive to the one stretch goal
    seasons: dict[str, list] = {}
    for g in out:
        if g["id"] != "stretch":
            seasons.setdefault(g["due"], []).append(g)
    return {
        "stretch": next((g for g in out if g["id"] == "stretch"), None),
        "seasons": [{"due": d, "goals": gs} for d, gs in seasons.items()],
    }


@router.put("/money/goals/{goal_id}")
def set_goal(request: Request, goal_id: str = GOAL_ID, body: GoalIn = ...):
    if body.target_cents == 0 and body.kind != "cards_owed":
        raise HTTPException(422, "target must be above 0")
    if body.kind == "income_since" and body.start is None:
        raise HTTPException(422, "an income_since goal needs a start date")
    # floor is a generic "don't let the bar read below this" marker (the stretch card draws it
    # regardless of kind), not specific to any one kind
    if body.floor_cents is not None and body.floor_cents >= body.target_cents:
        raise HTTPException(422, "floor must be below the target")
    with request.app.state.session_factory() as db:
        if body.kind == "account" and (
            body.account_id is None or db.get(BankAccount, body.account_id) is None
        ):
            raise HTTPException(422, "account goal needs an existing account")
        db.merge(SavingsGoal(id=goal_id, **body.model_dump()))
        db.commit()
    return {"id": goal_id}


@router.delete("/money/goals/{goal_id}")
def delete_goal(request: Request, goal_id: str = GOAL_ID):
    with request.app.state.session_factory() as db:
        g = db.get(SavingsGoal, goal_id)
        if g is None:
            raise HTTPException(404, "not found")
        db.delete(g)
        db.commit()
    return {"deleted": goal_id}
