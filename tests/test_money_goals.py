"""Spec 16 goals tab: savings, investing and stretch goals read from balances and income."""

from tests.test_banks import H
from tests.test_money_overview import ready

DUE = "2026-12-31"


def acct(c, name):
    return next(a for a in c.get("/banks", headers=H).json()["accounts"] if a["nickname"] == name)


def put(c, gid, **body):
    return c.put(f"/money/goals/{gid}", headers=H, json={"due": DUE} | body)


def test_AC16_16_input_is_validated(tmp_path):
    app, c = ready(tmp_path)
    assert put(c, "x", name="a", kind="net_worth", target_cents=0).status_code == 422
    assert put(c, "x", name="a", kind="net_worth", target_cents=-1).status_code == 422
    assert put(c, "x", name="a", kind="cards_owed", target_cents=0).status_code == 200
    assert (
        c.put(
            "/money/goals/x", headers=H, json={"name": "a", "kind": "net_worth", "target_cents": 1}
        ).status_code
        == 422
    )
    assert put(c, "x", name="a", kind="account", target_cents=100).status_code == 422
    assert (
        put(c, "x", name="a", kind="account", account_id=999, target_cents=100).status_code == 422
    )
    assert put(c, "x", name="a", kind="nope", target_cents=100).status_code == 422
    assert c.delete("/money/goals/missing", headers=H).status_code == 404


def test_AC16_17_current_amounts_come_from_balances_and_income(tmp_path):
    app, c = ready(tmp_path)
    sav = acct(c, "Savings")["id"]
    assert (
        put(
            c, "em", name="emergency", kind="account", account_id=sav, target_cents=1_000_000
        ).status_code
        == 200
    )
    put(c, "nw", name="net worth", kind="net_worth", target_cents=5_000_000)
    put(c, "inv", name="roth", kind="invested", target_cents=4_000_000)
    put(c, "cc", name="cards", kind="cards_owed", target_cents=0)
    put(
        c,
        "st",
        name="stretch",
        kind="income_since",
        start="2026-11-01",
        target_cents=60_600_000,
        floor_cents=10_000_000,
    )
    g = {x["id"]: x for s in c.get("/money/goals", headers=H).json()["seasons"] for x in s["goals"]}
    stretch = c.get("/money/goals", headers=H).json()["stretch"]
    assert g["em"]["current_cents"] == 500_000 and g["em"]["fraction"] == 0.5
    # 1234.56 + 5000 + 20000 - 300 owed on the card
    assert g["nw"]["current_cents"] == 2_593_456
    assert g["inv"]["current_cents"] == 2_000_000
    assert g["cc"]["current_cents"] == 30_000 and g["cc"]["met"] is False
    # only the november paycheck is on or after the start date
    assert stretch["current_cents"] == 210_000 and stretch["floor_cents"] == 10_000_000
    card = acct(c, "Card")["id"]
    c.patch(f"/banks/accounts/{card}", headers=H, json={"enabled": False})
    g = {x["id"]: x for s in c.get("/money/goals", headers=H).json()["seasons"] for x in s["goals"]}
    assert g["cc"]["met"] is True and g["nw"]["current_cents"] == 2_623_456


def test_AC16_18_grouped_by_due_date_and_needs_token(tmp_path):
    app, c = ready(tmp_path)
    put(c, "b", name="later", kind="net_worth", target_cents=100, due="2027-05-31")
    put(c, "a", name="sooner", kind="net_worth", target_cents=100, due="2026-12-31")
    put(c, "c", name="also sooner", kind="invested", target_cents=100, due="2026-12-31")
    seasons = c.get("/money/goals", headers=H).json()["seasons"]
    assert [s["due"] for s in seasons] == ["2026-12-31", "2027-05-31"]
    assert [g["id"] for g in seasons[0]["goals"]] == ["a", "c"]
    assert c.delete("/money/goals/a", headers=H).status_code == 200
    for m, u in [("GET", "/money/goals"), ("PUT", "/money/goals/a"), ("DELETE", "/money/goals/a")]:
        assert c.request(m, u, json={}).status_code == 401, u


def test_AC16_19_one_stretch_goal_with_floor_below_target(tmp_path):
    app, c = ready(tmp_path)
    ok = dict(name="s", kind="income_since", start="2026-11-25", target_cents=1000, floor_cents=500)
    assert put(c, "s1", **ok).status_code == 200
    assert (
        put(c, "s1", **ok | {"target_cents": 2000}).status_code == 200
    )  # replacing the same one is fine
    assert put(c, "s2", **ok).status_code == 409
    assert put(c, "s1", **ok | {"floor_cents": 1000}).status_code == 422
    assert put(c, "s1", **ok | {"start": None}).status_code == 422
    assert c.get("/money/goals", headers=H).json()["seasons"] == []
