import json
import logging
import time
from datetime import UTC, datetime

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.allowlist import RULES
from app.clock import FixedClock, get_clock
from app.config import Settings
from app.db import Base
from app.http_client import GuardedHttpClient, RequestDenied
from app.main import create_app
from app.models import BankAccount, BankItem, Transaction
from app.sources.plaid import PlaidClient

NOW = datetime(2026, 11, 19, 15, 0, tzinfo=UTC)
H = {"Authorization": "Bearer tok"}
TOKEN = "access-sandbox-SECRETTOKEN123"
KEY = Fernet.generate_key().decode()


def tx(id, acct, amount, d, name="Coffee Shop", pending=False, pending_id=None):
    return {
        "transaction_id": id,
        "account_id": acct,
        "amount": amount,
        "date": d,
        "name": name,
        "merchant_name": name,
        "pending": pending,
        "pending_transaction_id": pending_id,
        "personal_finance_category": {"primary": "FOOD_AND_DRINK"},
    }


class FakePlaid:
    def __init__(self, pages=None):
        self.pages = pages or [
            {"added": [], "modified": [], "removed": [], "next_cursor": "c1", "has_more": False}
        ]
        self.removed, self.cursors = [], []

    def link_token_create(self, access_token=None):
        if access_token:
            return {"link_token": "relink-1", "hosted_link_url": "https://hosted.plaid.test/re"}
        return {"link_token": "link-1", "hosted_link_url": "https://hosted.plaid.test/x"}

    def link_token_public_token(self, link_token):
        return "public-1" if link_token in ("link-1", "relink-1") else None

    def sandbox_public_token(self):
        return "public-sbx"

    def exchange(self, public_token):
        return TOKEN, "item-1"

    def accounts(self, access_token):
        assert access_token == TOKEN
        return (
            "ins_1",
            "First Platypus Bank",
            [
                {"account_id": "a1", "name": "Checking", "mask": "0000"},
                {"account_id": "a2", "name": "Savings", "mask": "1111"},
                {"account_id": "a3", "name": "Credit Card", "mask": "2222"},
            ],
        )

    def transactions_sync(self, access_token, cursor):
        self.cursors.append(cursor)
        return self.pages.pop(0) if len(self.pages) > 1 else self.pages[0]

    def item_remove(self, access_token):
        self.removed.append(access_token)


def build(tmp_path, plaid=None, **kw):
    s = Settings(
        _env_file=None,
        api_token="tok",
        database_url=f"sqlite:///{tmp_path}/t.db",
        token_encryption_key=KEY,
        plaid_client_id="cid",
        plaid_secret="SECRETPLAIDSECRET",
        **kw,
    )
    app = create_app(s, sources={}, plaid=plaid or FakePlaid())
    Base.metadata.create_all(app.state.session_factory.kw["bind"])
    app.dependency_overrides[get_clock] = lambda: FixedClock(NOW)
    return app, TestClient(app)


def connect(c):
    r = c.post("/banks/connect", headers=H).json()
    return c.post("/banks/connect/complete", headers=H, json={"link_token": r["link_token"]})


def sync(app):
    return app.state.runner.run_sync("banks")


def txs(c, **params):
    return c.get("/transactions", headers=H, params=params).json()


PAGE = {
    "added": [
        tx("t1", "a1", 12.5, "2026-11-18", "Chipotle"),
        tx("t2", "a1", -1200.00, "2026-11-18", "Payroll"),
        tx("t3", "a2", 4.99, "2026-11-17", "Netflix"),
        tx("t4", "a3", 60.1, "2026-11-19", "Shell Gas"),
    ],
    "modified": [],
    "removed": [],
    "next_cursor": "c1",
    "has_more": False,
}


def test_AC16_1_three_accounts_newest_first(tmp_path):
    app, c = build(tmp_path, FakePlaid([PAGE]))
    assert connect(c).status_code == 200
    sync(app)
    j = txs(c)
    dates = [t["date"] for t in j["transactions"]]
    assert dates == sorted(dates, reverse=True) and dates[0] == "2026-11-19"
    assert {t["bank"] for t in j["transactions"]} == {"First Platypus Bank"}
    assert len(j["transactions"]) == 4 and not j["demo"]


def test_AC16_2_cents_and_display(tmp_path):
    app, c = build(tmp_path, FakePlaid([PAGE]))
    connect(c)
    sync(app)
    by = {t["merchant"]: t for t in txs(c)["transactions"]}
    assert by["Chipotle"]["amount"] == "12.50" and by["Chipotle"]["direction"] == "out"
    assert by["Payroll"]["amount"] == "+1200.00" and by["Payroll"]["direction"] == "in"
    with app.state.session_factory() as db:
        row = db.scalars(select(Transaction).where(Transaction.merchant == "Chipotle")).one()
        assert row.amount_cents == 1250 and isinstance(row.amount_cents, int)


def test_AC16_3_pending_then_posted_no_duplicate(tmp_path):
    pend = {
        "added": [tx("p1", "a1", 8.0, "2026-11-19", "Cafe", pending=True)],
        "modified": [],
        "removed": [],
        "next_cursor": "c1",
        "has_more": False,
    }
    post = {
        "added": [tx("t9", "a1", 8.0, "2026-11-19", "Cafe", pending_id="p1")],
        "modified": [],
        "removed": [{"transaction_id": "p1"}],
        "next_cursor": "c2",
        "has_more": False,
    }
    fp = FakePlaid([pend, post])
    app, c = build(tmp_path, fp)
    connect(c)
    sync(app)
    assert txs(c)["transactions"][0]["pending"] is True
    sync(app)
    j = txs(c)["transactions"]
    assert len(j) == 1 and j[0]["pending"] is False
    assert fp.cursors == [None, "c1"]


def test_AC16_4_bank_filter_and_chip(tmp_path):
    app, c = build(tmp_path, FakePlaid([PAGE]))
    connect(c)
    sync(app)
    banks = c.get("/banks", headers=H).json()
    assert banks["chip"] == "banks: all" and len(banks["accounts"]) == 3
    acct = next(a for a in banks["accounts"] if a["nickname"] == "Savings")
    assert (
        c.patch(f"/banks/accounts/{acct['id']}", headers=H, json={"enabled": False}).status_code
        == 200
    )
    assert c.get("/banks", headers=H).json()["chip"] == "banks: 2 of 3"
    assert "Netflix" not in [t["merchant"] for t in txs(c)["transactions"]]


def test_reauth_uses_update_mode_and_resyncs_on_completion(tmp_path):
    fp = FakePlaid([PAGE])
    app, c = build(tmp_path, fp)
    item_id = connect(c).json()["id"]
    r = c.post(f"/banks/{item_id}/reauth", headers=H)
    assert r.status_code == 200
    assert r.json() == {"link_token": "relink-1", "hosted_link_url": "https://hosted.plaid.test/re"}

    not_done = c.post(f"/banks/{item_id}/reauth/complete", headers=H, json={"link_token": "nope"})
    assert not_done.status_code == 409

    done = c.post(f"/banks/{item_id}/reauth/complete", headers=H, json={"link_token": "relink-1"})
    assert done.status_code == 200
    assert txs(c)["transactions"]  # the resync it triggers actually ran


def test_reauth_unknown_bank_is_404(tmp_path):
    app, c = build(tmp_path, FakePlaid([PAGE]))
    assert c.post("/banks/999/reauth", headers=H).status_code == 404


class Spy:
    def __init__(self):
        self.bodies = []


def _plaid_with_transport(handler):
    s = Settings(
        _env_file=None,
        api_token="tok",
        database_url="sqlite://",
        plaid_client_id="cid",
        plaid_secret="SECRETPLAIDSECRET",
    )
    http = GuardedHttpClient(
        type("S", (), {"record": lambda *a, **k: None})(),
        rules=RULES,
        transport=httpx.MockTransport(handler),
    )
    return PlaidClient(http, s), http


def test_AC16_5_only_transactions_product_and_no_payment_paths():
    seen = []

    def handler(req):
        seen.append((str(req.url), json.loads(req.content)))
        return httpx.Response(200, json={"link_token": "l", "hosted_link_url": "u"})

    p, http = _plaid_with_transport(handler)
    p.link_token_create()
    url, body = seen[0]
    assert url.startswith("https://sandbox.plaid.com/") and body["products"] == ["transactions"]
    for bad in (["transfer"], ["payment_initiation"], ["transactions", "auth"]):
        with pytest.raises(RequestDenied):
            http.request(
                "plaid",
                "POST",
                "https://sandbox.plaid.com/link/token/create",
                json={"products": bad},
            )
        with pytest.raises(RequestDenied):
            http.request(
                "plaid",
                "POST",
                "https://sandbox.plaid.com/sandbox/public_token/create",
                json={"initial_products": bad},
            )
    for path in (
        "/transfer/create",
        "/payment_initiation/payment/create",
        "/processor/token/create",
    ):
        with pytest.raises(RequestDenied):
            http.request("plaid", "POST", "https://sandbox.plaid.com" + path, json={})
    with pytest.raises(RequestDenied):  # sandbox helper never allowed on the real host
        http.request(
            "plaid", "POST", "https://production.plaid.com/sandbox/public_token/create", json={}
        )


def test_AC16_6_token_encrypted_and_never_leaks(tmp_path, caplog):
    app, c = build(tmp_path, FakePlaid([PAGE]))
    with caplog.at_level(logging.DEBUG):
        connect(c)
        sync(app)
        bodies = [c.get(u, headers=H).text for u in ("/banks", "/transactions")]
    with app.state.session_factory() as db:
        raw = db.execute(text("select access_token_enc from bank_items")).scalar()
    assert TOKEN not in raw and raw
    assert all(TOKEN not in b for b in bodies) and TOKEN not in caplog.text


def test_AC16_7_logs_have_no_merchants_or_amounts(tmp_path, caplog):
    app, c = build(tmp_path, FakePlaid([PAGE]))
    with caplog.at_level(logging.DEBUG):
        connect(c)
        sync(app)
        txs(c)
    for needle in ("Chipotle", "Netflix", "12.5", "1200", "0000", "SECRETPLAIDSECRET"):
        assert needle not in caplog.text


def test_AC16_8_delete_removes_everything(tmp_path):
    fp = FakePlaid([PAGE])
    app, c = build(tmp_path, fp)
    connect(c)
    sync(app)
    with app.state.session_factory() as db:
        item_id = db.scalars(select(BankItem.id)).one()
    assert c.delete(f"/banks/{item_id}", headers=H).status_code == 200
    assert fp.removed == [TOKEN]
    with app.state.session_factory() as db:
        for m in (BankItem, BankAccount, Transaction):
            assert db.scalars(select(m)).first() is None


def test_AC16_9_ask_money_is_off_unless_enabled(tmp_path):
    app, c = build(tmp_path, FakePlaid([PAGE]))
    connect(c)
    sync(app)
    off = c.post(
        "/ask",
        headers=H,
        json={"question": "how much did I spend at Chipotle", "context": ["vault", "calendar"]},
    ).json()
    assert "money" in off["answer"].lower() and "off" in off["answer"].lower()
    on = c.post(
        "/ask",
        headers=H,
        json={"question": "how much did I spend at Chipotle", "context": ["money"]},
    ).json()
    assert "Chipotle" not in on["answer"] and "12.50" not in on["answer"]


def test_AC16_10_demo_data_when_nothing_connected(tmp_path):
    app, c = build(tmp_path)
    j = txs(c)
    assert j["demo"] is True and j["note"] and j["transactions"]


def test_AC16_11_auth(tmp_path):
    app, c = build(tmp_path)
    for method, url in [
        ("get", "/transactions"),
        ("get", "/banks"),
        ("post", "/banks/connect"),
        ("post", "/banks/connect/complete"),
        ("delete", "/banks/1"),
        ("post", "/banks/sandbox"),
        ("patch", "/banks/accounts/1"),
    ]:
        assert c.request(method.upper(), url, json={}).status_code == 401, url


def test_AC16_12_5000_transactions_paged_fast(tmp_path):
    big = {
        "added": [
            tx(f"t{i}", "a1", 1.0 + i % 50, f"2026-{1 + i % 11:02d}-{1 + i % 27:02d}", f"M{i}")
            for i in range(5000)
        ],
        "modified": [],
        "removed": [],
        "next_cursor": "c",
        "has_more": False,
    }
    app, c = build(tmp_path, FakePlaid([big]))
    connect(c)
    sync(app)
    t = time.perf_counter()
    first = txs(c, limit=50)
    assert (
        time.perf_counter() - t < 1.0 and len(first["transactions"]) == 50 and first["next_cursor"]
    )
    seen, cur = set(), None
    while True:
        j = txs(c, limit=500, **({"cursor": cur} if cur else {}))
        seen |= {t["id"] for t in j["transactions"]}
        cur = j["next_cursor"]
        if not cur:
            break
    assert len(seen) == 5000


def test_sandbox_endpoint_only_in_sandbox(tmp_path):
    app, c = build(tmp_path, FakePlaid([PAGE]))
    assert c.post("/banks/sandbox", headers=H).status_code == 200
    sync(app)
    assert len(txs(c)["transactions"]) == 4
    (tmp_path / "prod").mkdir()
    app2, c2 = build(tmp_path / "prod", FakePlaid([PAGE]), plaid_env="production")
    assert c2.post("/banks/sandbox", headers=H).status_code == 404


def test_default_sources_add_banks_only_when_plaid_configured():
    from app.jobs.runner import default_sources

    s = Settings(_env_file=None, api_token="tok", database_url="sqlite://")
    assert "banks" not in default_sources(s, http=None)
    assert "banks" in default_sources(s, http=None, plaid=FakePlaid())
