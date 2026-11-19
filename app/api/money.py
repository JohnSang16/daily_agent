"""Money overview: spend vs income, categories, holdings, and monthly budget goals."""

from datetime import date
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.auth import require_token
from app.clock import Clock, get_clock
from app.models import Budget
from app.money import holdings, last_months, month_totals

router = APIRouter(dependencies=[Depends(require_token)])


def _today(request: Request, clock: Clock) -> date:
    return clock.now().astimezone(ZoneInfo(request.app.state.settings.user_timezone)).date()


@router.get("/money/summary")
def summary(
    request: Request, months: int = Query(6, ge=1, le=24), clock: Clock = Depends(get_clock)
):
    keys = last_months(_today(request, clock), months)
    with request.app.state.session_factory() as db:
        totals, cats = month_totals(db, keys)
        now = totals[keys[-1]]
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
        }


class BudgetIn(BaseModel):
    limit_cents: int = Field(gt=0, le=100_000_000)


CATEGORY = Path(pattern=r"^[A-Z_]{2,40}$")


@router.get("/budgets")
def list_budgets(request: Request, clock: Clock = Depends(get_clock)):
    keys = last_months(_today(request, clock), 1)
    with request.app.state.session_factory() as db:
        totals, cats = month_totals(db, keys)
        rows = db.scalars(select(Budget)).all()

        def spent(b: Budget) -> int:
            return totals[keys[0]]["spend"] if b.category == "TOTAL" else cats.get(b.category, 0)

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
