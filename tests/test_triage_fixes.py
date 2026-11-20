"""One test per backend bug in docs/TRIAGE.md (2026-11-19). Each failed before its fix."""

from datetime import UTC, date, datetime, timedelta

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.banks import store_item, sync_banks
from app.clock import FixedClock, get_clock
from app.config import Settings
from app.crypto import TokenBox
from app.db import Base, make_session_factory
from app.llm.client import LlmResult
from app.llm.explain import build_payload, explain
from app.main import create_app
from app.models import BankAccount, BankItem, Event, ExplanationCache, SyncRun, Task, Transaction
from app.money import is_internal
from app.schemas import TaskIn
from app.sources.google_calendar import HttpCalendarClient, sync_google_calendar
from app.sources.icollege import parse_feed
from app.sources.obsidian import parse_line
from app.tasks_sync import sync_tasks

NY = "America/New_York"
NOW = datetime(2026, 11, 19, 15, 0, tzinfo=UTC)
H = {"Authorization": "Bearer tok"}
KEY = Fernet.generate_key().decode()


@pytest.fixture
def s():
    sf = make_session_factory("sqlite://")
    Base.metadata.create_all(sf.kw["bind"])
    with sf() as db:
        yield db


# 1. a multi day event that started before the window crashed every calendar sync
class OneEvent:
    def list_events(self, calendar_id, time_min, time_max, page_token=None):
        trip = {
            "id": "trip",
            "summary": "Finals week",
            "start": {"date": "2026-11-15"},
            "end": {"date": "2026-11-22"},
        }
        return [trip], None


def test_1_event_started_before_window_syncs_twice(s):
    for _ in range(3):
        sync_google_calendar(s, OneEvent(), NOW, NY, sleep=lambda _: None)
    rows = s.scalars(select(Event)).all()
    assert len(rows) == 1 and rows[0].status != "cancelled"


# 2. a bare calendar emoji crashed the whole vault sync
def test_2_calendar_emoji_without_date_needs_review():
    t = parse_line("- [ ] write essay 📅", "a.md", 1, NY)
    assert t is not None and t.needs_review and t.review_reason == "unreadable due date"


# 3 and 4. banks
class TwoBanks:
    """Two logins: 'good' and 'bad'. The bad one fails like an expired login."""

    def __init__(self):
        self.removed = []
        self.next_exchange = ("tok-good", "item-good", "ins_good")

    def exchange(self, public_token):
        return self.next_exchange[:2]

    def accounts(self, access):
        if access == "tok-bad":
            raise RuntimeError("ITEM_LOGIN_REQUIRED")
        ins = "ins_dup" if access == "tok-dup" else "ins_" + access.split("-")[1]
        return ins, ins, [{"account_id": access + "-a", "name": "Checking", "mask": "1"}]

    def transactions_sync(self, access, cursor):
        t = {
            "transaction_id": access + "-t",
            "account_id": access + "-a",
            "amount": 5,
            "date": "2026-11-18",
            "name": "Coffee",
            "pending": False,
            "personal_finance_category": {"primary": "FOOD_AND_DRINK"},
        }
        return {"added": [t], "modified": [], "removed": [], "next_cursor": "c", "has_more": False}

    def item_remove(self, access):
        self.removed.append(access)


def _item(s, box, token, name, inst=None):
    s.add(
        BankItem(
            user_id=1,
            plaid_item_id=name,
            institution_id=inst or name,
            institution_name=name,
            access_token_enc=box.encrypt(token),
            created_at=NOW,
        )
    )
    s.commit()


def test_3_one_broken_bank_does_not_stop_the_others(s):
    box = TokenBox(KEY)
    _item(s, box, "tok-bad", "Bad Bank")
    _item(s, box, "tok-good", "Good Bank")
    with pytest.raises(RuntimeError):  # still reported as a failed run
        sync_banks(s, box, TwoBanks(), NOW)
    assert len(s.scalars(select(Transaction)).all()) == 1  # the good bank synced anyway


def test_4_connecting_the_same_bank_twice_is_refused(s):
    box, plaid = TokenBox(KEY), TwoBanks()
    plaid.next_exchange = ("tok-dup", "item-1")
    store_item(s, box, plaid, "public-1", NOW)
    plaid.next_exchange = ("tok-dup", "item-2")
    with pytest.raises(ValueError):
        store_item(s, box, plaid, "public-2", NOW)
    assert len(s.scalars(select(BankItem)).all()) == 1
    assert len(s.scalars(select(BankAccount)).all()) == 1
    assert plaid.removed == ["tok-dup"]  # the second login is closed at the aggregator


def test_4_api_says_409_for_a_bank_already_connected(tmp_path):
    plaid = TwoBanks()
    plaid.next_exchange = ("tok-dup", "item-1")
    plaid.link_token_public_token = lambda lt: "public"
    st = Settings(
        _env_file=None,
        api_token="tok",
        database_url=f"sqlite:///{tmp_path}/t.db",
        token_encryption_key=KEY,
        plaid_client_id="c",
        plaid_secret="s",
    )
    app = create_app(st, sources={}, plaid=plaid)
    Base.metadata.create_all(app.state.session_factory.kw["bind"])
    c = TestClient(app)
    body = {"link_token": "x"}
    assert c.post("/banks/connect/complete", headers=H, json=body).status_code == 200
    assert c.post("/banks/connect/complete", headers=H, json=body).status_code == 409


# 5. cash withdrawals are spending, real own-account transfers still are not
def test_5_atm_withdrawal_counts_as_spending():
    assert not is_internal("TRANSFER_OUT", "TRANSFER_OUT_WITHDRAWAL")
    assert is_internal("TRANSFER_OUT", "TRANSFER_OUT_ACCOUNT_TRANSFER")
    assert is_internal("TRANSFER_IN", "TRANSFER_IN_SAVINGS")
    assert is_internal("LOAN_PAYMENTS", "LOAN_PAYMENTS_CREDIT_CARD_PAYMENT")


def test_5_withdrawal_shows_in_the_spend_list(tmp_path):
    st = Settings(_env_file=None, api_token="tok", database_url=f"sqlite:///{tmp_path}/t.db")
    app = create_app(st, sources={})
    Base.metadata.create_all(app.state.session_factory.kw["bind"])
    with app.state.session_factory() as db:
        _item(db, TokenBox(KEY), "t", "Bank")
        db.add(BankAccount(item_id=1, account_id="a", nickname="C", mask="1", enabled=True))
        for i, detail in enumerate(["TRANSFER_OUT_WITHDRAWAL", "TRANSFER_OUT_ACCOUNT_TRANSFER"]):
            db.add(
                Transaction(
                    account_id=1,
                    source_id=f"t{i}",
                    posted_date=date(2026, 11, 18),
                    merchant="ATM",
                    amount_cents=4000,
                    direction="out",
                    category="TRANSFER_OUT",
                    category_detail=detail,
                    pending=False,
                    updated_at=NOW,
                )
            )
        db.commit()
    j = TestClient(app).get("/transactions", headers=H, params={"kind": "spend"}).json()
    assert len(j["transactions"]) == 1


# 6. a missed assignment shows as overdue for a while instead of vanishing
def test_6_recently_missed_assignment_is_kept():
    ics = (
        "BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nSUMMARY:HW 7 - Due\r\nDTSTART:20261117T045900Z\r\n"
        "END:VEVENT\r\nBEGIN:VEVENT\r\nSUMMARY:Old - Due\r\nDTSTART:20261001T045900Z\r\n"
        "END:VEVENT\r\nEND:VCALENDAR\r\n"
    )
    assert [t.title for t in parse_feed(ics, NOW)] == ["HW 7"]


# 7. done in the app resets once the line is deleted from the source
def test_7_done_in_app_resets_after_the_source_deletes_it(s):
    item = TaskIn(title="Essay", scope="a.md", source_ref="a.md:1", due_date=date(2026, 11, 25))
    sync_tasks(s, "obsidian", "a.md", [item], NOW, NY)
    t = s.scalars(select(Task)).one()
    t.locally_done, t.status = True, "done"
    s.commit()
    sync_tasks(s, "obsidian", "a.md", [], NOW, NY)  # deleted from the note
    sync_tasks(s, "obsidian", "a.md", [item], NOW, NY)  # written again later
    assert s.scalars(select(Task)).one().status == "open"


# 8. two requests explaining the same ranking at once must not crash
def test_8_explanation_cache_race_does_not_crash(tmp_path):
    sf = make_session_factory(f"sqlite:///{tmp_path}/t.db")
    Base.metadata.create_all(sf.kw["bind"])
    payload = build_payload(
        [{"title": "Essay", "due_local": None, "reasons": [], "at_risk": False}]
    )

    class RacingLlm:
        def complete(self, prompt):
            with sf() as other:  # another request finished first and cached the same key
                import hashlib
                import json

                key = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
                other.add(ExplanationCache(key=key, text="Start with Essay.", created_at=NOW))
                other.commit()
            return LlmResult("Start with Essay now.", 10, 5)

    with sf() as db:
        text, source, _ = explain(db, RacingLlm(), "m", 10_000, payload, NOW, NOW)
    assert "Essay" in text and source == "llm"


# 9. calendar ids with # (holiday calendars) built the wrong path
def test_9_calendar_id_with_hash_is_escaped(tmp_path):
    seen = []

    class Http:
        def get(self, integration, url, **kw):
            seen.append(url)

            class R:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    return {"items": []}

            return R()

    c = HttpCalendarClient.__new__(HttpCalendarClient)
    c.http, c.token = Http(), {"access_token": "x"}
    c.list_events("en.usa#holiday@group.v.calendar.google.com", NOW, NOW)
    assert "%23" in seen[0] and "#" not in seen[0]


# 10. /today hides titles under every blocked glob, not only cox/
def test_10_today_respects_blocked_globs(tmp_path):
    class Spy:
        prompts = []

        def complete(self, prompt):
            self.prompts.append(prompt)
            return LlmResult("Start with Private task.", 10, 5)

    spy = Spy()
    st = Settings(
        _env_file=None,
        api_token="tok",
        database_url=f"sqlite:///{tmp_path}/t.db",
        ask_llm_blocked_globs="cox/*,health/*",
    )
    app = create_app(st, llm=spy, sources={})
    Base.metadata.create_all(app.state.session_factory.kw["bind"])
    app.dependency_overrides[get_clock] = lambda: FixedClock(NOW)
    item = TaskIn(
        title="Therapy intake form",
        scope="health/a.md",
        source_ref="x",
        due_date=date(2026, 11, 25),
    )
    with app.state.session_factory() as db:
        sync_tasks(db, "obsidian", "health/a.md", [item], NOW, NY)
    TestClient(app).get("/today", headers=H)
    assert spy.prompts and "Therapy" not in spy.prompts[0]


# 11. the week strip can ask for more than 50 ranked tasks
def test_11_today_limit_allows_a_full_week(tmp_path):
    st = Settings(_env_file=None, api_token="tok", database_url=f"sqlite:///{tmp_path}/t.db")
    app = create_app(st, sources={})
    Base.metadata.create_all(app.state.session_factory.kw["bind"])
    assert TestClient(app).get("/today?limit=500", headers=H).status_code == 200


# 12. manual items are validated
@pytest.mark.parametrize(
    "body",
    [
        {"kind": "task", "title": "x", "effort_minutes": -30},
        {"kind": "task", "title": "x", "effort_minutes": 0},
        {"kind": "task", "title": "x" * 301},
        {"kind": "task", "title": "   "},
        {"kind": "task", "title": "x", "importance": 9},
    ],
)
def test_12_bad_manual_items_are_rejected(tmp_path, body):
    st = Settings(_env_file=None, api_token="tok", database_url=f"sqlite:///{tmp_path}/t.db")
    app = create_app(st, sources={})
    Base.metadata.create_all(app.state.session_factory.kw["bind"])
    assert TestClient(app).post("/items", headers=H, json=body).status_code == 422


# 13. warnings use the latest run per source, not the whole history
def test_13_warnings_follow_the_latest_run(tmp_path):
    from app.api.today import _warnings

    sf = make_session_factory(f"sqlite:///{tmp_path}/t.db")
    Base.metadata.create_all(sf.kw["bind"])
    with sf() as db:
        for i in range(300):
            at = NOW - timedelta(minutes=300 - i)
            db.add(SyncRun(source="obsidian", started_at=at, finished_at=at, status="ok"))
        old = NOW - timedelta(hours=1, minutes=1)
        db.add(SyncRun(source="banks", started_at=old, finished_at=old, status="error"))
        db.add(SyncRun(source="banks", started_at=NOW, finished_at=NOW, status="ok"))
        db.commit()
        assert _warnings(db, NOW, 26, 0) == []


# 14. a bank can be deleted locally even without the encryption key
def test_14_delete_bank_without_the_key(tmp_path):
    st = Settings(_env_file=None, api_token="tok", database_url=f"sqlite:///{tmp_path}/t.db")
    app = create_app(st, sources={})
    Base.metadata.create_all(app.state.session_factory.kw["bind"])
    with app.state.session_factory() as db:
        _item(db, TokenBox(KEY), "t", "Bank")
    r = TestClient(app).delete("/banks/1", headers=H)
    assert r.status_code == 200 and r.json()["remote_removed"] is False
    with app.state.session_factory() as db:
        assert db.scalars(select(BankItem)).first() is None


# found during the fixes: the vault checkout lost its deploy key after the first clone
def test_vault_checkout_uses_an_absolute_key_and_keeps_path(tmp_path, monkeypatch):
    import subprocess

    from app.sources import vault_checkout

    calls = []

    def fake_run(args, **kw):
        calls.append(kw)
        return subprocess.CompletedProcess(args, 0, stdout="main\n")

    monkeypatch.setattr(vault_checkout.subprocess, "run", fake_run)
    (tmp_path / "co" / ".git").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    vault_checkout.ensure_checkout("git@x:y.git", "./secrets/key", str(tmp_path / "co"))
    env = calls[0]["env"]
    assert f"-i {tmp_path.resolve()}/secrets/key " in env["GIT_SSH_COMMAND"]
    assert "PATH" in env
