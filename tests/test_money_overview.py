from sqlalchemy import inspect, text

from tests.test_banks import FakePlaid, H, build, connect, sync

CC = "LOAN_PAYMENTS_CREDIT_CARD_PAYMENT"


def t(id, acct, amount, d, cat, detail=None, name="Shop"):
    return {
        "transaction_id": id,
        "account_id": acct,
        "amount": amount,
        "date": d,
        "name": name,
        "merchant_name": name,
        "pending": False,
        "pending_transaction_id": None,
        "personal_finance_category": {"primary": cat, "detailed": detail or cat},
    }


class Plaid2(FakePlaid):
    def accounts(self, access_token):
        return (
            "ins_1",
            "First Bank",
            [
                {
                    "account_id": "a1",
                    "name": "Checking",
                    "mask": "0000",
                    "type": "depository",
                    "subtype": "checking",
                    "balances": {"current": 1234.56},
                },
                {
                    "account_id": "a2",
                    "name": "Card",
                    "mask": "2222",
                    "type": "credit",
                    "subtype": "credit card",
                    "balances": {"current": 300.0},
                },
                {
                    "account_id": "a3",
                    "name": "Savings",
                    "mask": "1111",
                    "type": "depository",
                    "subtype": "savings",
                    "balances": {"current": 5000.0},
                },
                {
                    "account_id": "a4",
                    "name": "Brokerage",
                    "mask": "4444",
                    "type": "investment",
                    "subtype": "brokerage",
                    "balances": {"current": 20000.0},
                },
            ],
        )


PAGE = {
    "added": [
        # October
        t("o1", "a1", -2000.00, "2026-10-15", "INCOME", name="Paycheck"),
        t("o2", "a1", 100.00, "2026-10-10", "FOOD_AND_DRINK"),
        t("o3", "a1", 500.00, "2026-10-12", "TRANSFER_OUT"),
        t("o4", "a2", -500.00, "2026-10-12", "TRANSFER_IN"),
        t("o5", "a1", 300.00, "2026-10-20", "LOAN_PAYMENTS", CC, name="Card payment"),
        t("o6", "a2", -300.00, "2026-10-20", "LOAN_PAYMENTS", CC, name="Card payment"),
        # November
        t("n1", "a1", -2100.00, "2026-11-05", "INCOME", name="Paycheck"),
        t("n2", "a2", 40.00, "2026-11-06", "FOOD_AND_DRINK"),
        t("n3", "a2", 60.00, "2026-11-07", "GENERAL_MERCHANDISE"),
        t("n4", "a2", -20.00, "2026-11-08", "GENERAL_MERCHANDISE", name="Refund"),
        t("n5", "a1", 30.00, "2026-11-09", "TRANSPORTATION"),
    ],
    "modified": [],
    "removed": [],
    "next_cursor": "c",
    "has_more": False,
}


def ready(tmp_path):
    app, c = build(tmp_path, Plaid2([PAGE]))
    connect(c)
    sync(app)
    return app, c


def test_summary_by_month_skips_transfers_and_card_payments(tmp_path):
    app, c = ready(tmp_path)
    j = c.get("/money/summary?months=6", headers=H).json()
    by = {m["month"]: m for m in j["months"]}
    assert [m["month"] for m in j["months"]] == [
        "2026-06",
        "2026-07",
        "2026-08",
        "2026-09",
        "2026-10",
        "2026-11",
    ]
    assert by["2026-06"] == {"month": "2026-06", "income_cents": 0, "spend_cents": 0}
    assert by["2026-10"]["income_cents"] == 200000 and by["2026-10"]["spend_cents"] == 10000
    # november: 40 food + (60 - 20 refund) merchandise + 30 transport
    assert by["2026-11"]["income_cents"] == 210000 and by["2026-11"]["spend_cents"] == 11000
    assert j["this_month"] == {
        "month": "2026-11",
        "income_cents": 210000,
        "spend_cents": 11000,
        "net_cents": 199000,
    }


def test_categories_this_month_sorted_largest_first(tmp_path):
    app, c = ready(tmp_path)
    cats = c.get("/money/summary", headers=H).json()["categories"]
    assert [(x["category"], x["spend_cents"]) for x in cats] == [
        ("FOOD_AND_DRINK", 4000),
        ("GENERAL_MERCHANDISE", 4000),
        ("TRANSPORTATION", 3000),
    ]


def test_a_disabled_account_leaves_the_totals(tmp_path):
    app, c = ready(tmp_path)
    card = next(a for a in c.get("/banks", headers=H).json()["accounts"] if a["nickname"] == "Card")
    c.patch(f"/banks/accounts/{card['id']}", headers=H, json={"enabled": False})
    assert c.get("/money/summary", headers=H).json()["this_month"]["spend_cents"] == 3000


def test_budgets_show_spent_this_month(tmp_path):
    app, c = ready(tmp_path)
    assert (
        c.put("/budgets/FOOD_AND_DRINK", headers=H, json={"limit_cents": 5000}).status_code == 200
    )
    assert c.put("/budgets/TOTAL", headers=H, json={"limit_cents": 20000}).status_code == 200
    b = {x["category"]: x for x in c.get("/budgets", headers=H).json()}
    assert b["FOOD_AND_DRINK"]["spent_cents"] == 4000 and b["FOOD_AND_DRINK"]["limit_cents"] == 5000
    assert b["TOTAL"]["spent_cents"] == 11000
    assert c.delete("/budgets/FOOD_AND_DRINK", headers=H).status_code == 200
    assert [x["category"] for x in c.get("/budgets", headers=H).json()] == ["TOTAL"]


def test_budget_input_is_validated(tmp_path):
    app, c = build(tmp_path)
    assert c.put("/budgets/FOOD_AND_DRINK", headers=H, json={"limit_cents": 0}).status_code == 422
    assert c.put("/budgets/FOOD_AND_DRINK", headers=H, json={"limit_cents": -5}).status_code == 422
    assert c.put("/budgets/food drink!", headers=H, json={"limit_cents": 100}).status_code == 422
    assert c.delete("/budgets/NOPE", headers=H).status_code == 404


def test_banks_list_has_balances_and_kinds(tmp_path):
    app, c = ready(tmp_path)
    a = {x["nickname"]: x for x in c.get("/banks", headers=H).json()["accounts"]}
    assert a["Checking"]["balance_cents"] == 123456 and a["Checking"]["kind"] == "depository"
    assert a["Card"]["balance_cents"] == 30000 and a["Card"]["kind"] == "credit"


def test_income_log_is_paychecks_only_newest_first(tmp_path):
    app, c = ready(tmp_path)
    rows = c.get("/transactions?kind=income&limit=50", headers=H).json()["transactions"]
    assert [(r["date"], r["amount"]) for r in rows] == [
        ("2026-11-05", "+2100.00"),
        ("2026-10-15", "+2000.00"),
    ]


def test_spend_filter_excludes_internal_moves(tmp_path):
    app, c = ready(tmp_path)
    rows = c.get("/transactions?kind=spend&limit=50", headers=H).json()["transactions"]
    cats = {r["category"] for r in rows}
    assert "TRANSFER_OUT" not in cats and "INCOME" not in cats and len(rows) == 4


def test_new_endpoints_need_the_token(tmp_path):
    app, c = build(tmp_path)
    for method, url in [
        ("get", "/money/summary"),
        ("get", "/budgets"),
        ("put", "/budgets/TOTAL"),
        ("delete", "/budgets/TOTAL"),
    ]:
        assert c.request(method.upper(), url, json={"limit_cents": 100}).status_code == 401, url


def test_migration_adds_the_new_columns_and_table(tmp_path):
    import subprocess
    import sys

    from sqlalchemy import create_engine

    url = f"sqlite:///{tmp_path}/m.db"
    env = {"DATABASE_URL": url, "API_TOKEN": "x", "PATH": "/usr/bin:/bin"}
    r = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert r.returncode == 0, r.stderr
    insp = inspect(create_engine(url))
    assert "budgets" in insp.get_table_names()
    assert {"type", "balance_cents"} <= {c["name"] for c in insp.get_columns("bank_accounts")}
    assert "category_detail" in {c["name"] for c in insp.get_columns("transactions")}
    assert text  # keep the import used


def test_holdings_group_cash_savings_invested_and_what_is_owed(tmp_path):
    app, c = ready(tmp_path)
    h = c.get("/money/summary", headers=H).json()["holdings"]
    assert h == {
        "cash_cents": 123456,
        "savings_cents": 500000,
        "invested_cents": 2000000,
        "credit_owed_cents": 30000,
        "loans_owed_cents": 0,
        "net_cents": 123456 + 500000 + 2000000 - 30000,
    }


def test_a_disabled_account_leaves_the_holdings(tmp_path):
    app, c = ready(tmp_path)
    inv = next(
        a for a in c.get("/banks", headers=H).json()["accounts"] if a["nickname"] == "Brokerage"
    )
    c.patch(f"/banks/accounts/{inv['id']}", headers=H, json={"enabled": False})
    assert c.get("/money/summary", headers=H).json()["holdings"]["invested_cents"] == 0
