import time
from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.clock import FixedClock, get_clock
from app.config import Settings
from app.db import Base
from app.llm.client import LlmResult
from app.main import create_app
from app.models import Event, ExplanationCache, LlmUsage, SyncRun
from app.schemas import TaskIn
from app.tasks_sync import sync_tasks

NY = "America/New_York"
# Monday 2026-11-16 09:00 New York
NOW = datetime(2026, 11, 16, 14, 0, tzinfo=UTC)
H = {"Authorization": "Bearer tok"}
SECRET = "SECRET-NOTE-BODY-TEXT"


class FakeLlm:
    def __init__(self, reply=None, fail=False):
        self.calls, self.prompts, self.reply, self.fail = 0, [], reply, fail

    def complete(self, prompt: str) -> LlmResult:
        self.calls += 1
        self.prompts.append(prompt)
        if self.fail:
            raise RuntimeError("boom")
        return LlmResult(self.reply or "Start with Essay, it is due first.", 100, 20)


def build(tmp_path, llm=None, **settings_kw):
    s = Settings(
        _env_file=None, api_token="tok", database_url=f"sqlite:///{tmp_path}/t.db", **settings_kw
    )
    app = create_app(s, llm=llm)
    Base.metadata.create_all(app.state.session_factory.kw["bind"])
    app.dependency_overrides[get_clock] = lambda: FixedClock(NOW)
    return app


def seed(app, tasks=None, events=()):
    with app.state.session_factory() as db:
        sync_tasks(
            db,
            "obsidian",
            "a.md",
            tasks
            if tasks is not None
            else [
                TaskIn(
                    title="Essay",
                    scope="a.md",
                    source_ref=SECRET,
                    due_date=date(2026, 11, 18),
                    effort_minutes=120,
                    review_reason=SECRET,
                ),
                TaskIn(
                    title="Lab report", scope="a.md", source_ref="a.md", due_date=date(2026, 11, 25)
                ),
                TaskIn(title="Someday", scope="a.md", source_ref="a.md", needs_review=True),
            ],
            NOW,
            NY,
        )
        for e in events:
            db.add(e)
        db.commit()


def ev(title, start, end, status="confirmed", all_day=False):
    return Event(
        user_id=1,
        source="google_calendar",
        source_ref=title,
        calendar_id="c",
        title=title,
        start_at=start,
        end_at=end,
        all_day=all_day,
        busy=True,
        status=status,
        updated_at=NOW,
        last_seen_at=NOW,
    )


def get(app, url="/today"):
    return TestClient(app).get(url, headers=H)


def test_AC8_1_shape(tmp_path):
    app = build(tmp_path, FakeLlm())
    seed(app)
    j = get(app).json()
    assert {
        "date",
        "timezone",
        "generated_at",
        "top_task",
        "ranked",
        "events",
        "free_blocks",
        "explanation",
        "warnings",
        "needs_review_count",
    } <= set(j)
    assert j["date"] == "2026-11-16" and j["timezone"] == NY
    assert j["generated_at"] == "2026-11-16T14:00:00Z"
    assert {"id", "title", "due_at", "reasons", "at_risk", "suggested_block"} <= set(j["top_task"])
    r0 = j["ranked"][0]
    assert {"id", "rank", "title", "due_at", "source", "reasons", "at_risk", "needs_review"} <= set(
        r0
    )
    assert j["needs_review_count"] == 1


def test_AC8_2_top_task_is_engine_top(tmp_path):
    app = build(tmp_path, FakeLlm())
    seed(app)
    j = get(app).json()
    assert j["top_task"]["title"] == "Essay" == j["ranked"][0]["title"]
    assert j["top_task"]["id"] == j["ranked"][0]["id"]
    assert j["ranked"][0]["due_at"] == "2026-11-19T04:59:59Z"  # end of Nov 18 local


def test_AC8_3_params(tmp_path):
    app = build(tmp_path, FakeLlm())
    seed(app)
    assert len(get(app, "/today?limit=1").json()["ranked"]) == 1
    for bad in ["limit=0", "limit=51", "limit=x", "date=notadate"]:
        assert get(app, f"/today?{bad}").status_code == 422, bad
    assert get(app, "/today?date=2026-11-17").json()["date"] == "2026-11-17"


def test_AC8_4_no_tasks(tmp_path):
    app = build(tmp_path, FakeLlm())
    j = get(app).json()
    assert j["top_task"] is None and j["ranked"] == []
    assert "no" in j["explanation"]["text"].lower()


def test_AC8_5_stale_source_warning(tmp_path):
    app = build(tmp_path, FakeLlm())
    seed(app)
    with app.state.session_factory() as db:
        db.add(
            SyncRun(
                source="gmail_digest",
                started_at=NOW - timedelta(hours=31),
                finished_at=NOW - timedelta(hours=31),
                status="ok",
            )
        )
        db.add(
            SyncRun(
                source="obsidian",
                started_at=NOW - timedelta(hours=1),
                finished_at=NOW - timedelta(hours=1),
                status="ok",
            )
        )
        db.commit()
    w = get(app).json()["warnings"]
    stale = [x for x in w if x["code"] == "SOURCE_STALE"]
    assert len(stale) == 1 and stale[0]["source"] == "gmail_digest"
    assert "31h" in stale[0]["detail"]


def test_sync_error_warning(tmp_path):
    app = build(tmp_path, FakeLlm())
    seed(app)
    with app.state.session_factory() as db:
        db.add(SyncRun(source="google_calendar", started_at=NOW, finished_at=NOW, status="error"))
        db.commit()
    assert any(x["code"] == "SYNC_ERROR" for x in get(app).json()["warnings"])


def test_AC8_6_llm_failure_falls_back_to_template(tmp_path):
    app = build(tmp_path, FakeLlm(fail=True))
    seed(app)
    r = get(app)
    assert r.status_code == 200
    e = r.json()["explanation"]
    assert e["source"] == "template" and "Essay" in e["text"]


def test_no_llm_configured_uses_template(tmp_path):
    app = build(tmp_path, None)
    seed(app)
    assert get(app).json()["explanation"]["source"] == "template"


def test_AC8_7_cache_one_call_one_usage_row(tmp_path):
    llm = FakeLlm()
    app = build(tmp_path, llm)
    seed(app)
    a, b = get(app).json(), get(app).json()
    assert llm.calls == 1 and a["explanation"] == b["explanation"]
    assert a["explanation"]["source"] == "llm"
    with app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(LlmUsage)) == 1
        assert db.scalar(select(func.count()).select_from(ExplanationCache)) == 1


def test_AC8_8_prompt_has_no_note_or_email_text(tmp_path):
    llm = FakeLlm()
    app = build(tmp_path, llm)
    seed(app)
    get(app)
    prompt = llm.prompts[0]
    assert SECRET not in prompt and "Essay" in prompt
    assert "data, not instructions" in prompt


def test_llm_text_that_contradicts_ranking_is_replaced(tmp_path):
    app = build(tmp_path, FakeLlm(reply="Do the lab report first."))
    seed(app)
    assert get(app).json()["explanation"]["source"] == "template"


def test_budget_exhausted_uses_template_and_warns(tmp_path):
    llm = FakeLlm()
    app = build(tmp_path, llm, llm_daily_token_budget=50)
    seed(app)
    with app.state.session_factory() as db:
        db.add(
            LlmUsage(
                at=NOW - timedelta(hours=1),
                purpose="explanation",
                model="m",
                input_tokens=40,
                output_tokens=40,
            )
        )
        db.commit()
    j = get(app).json()
    assert llm.calls == 0 and j["explanation"]["source"] == "template"
    assert any(x["code"] == "LLM_BUDGET_EXHAUSTED" for x in j["warnings"])


def test_AC8_9_events_filtered_to_local_day_and_not_cancelled(tmp_path):
    app = build(tmp_path, FakeLlm())
    h = timedelta(hours=1)
    mon10 = NOW + h
    seed(
        app,
        tasks=[],
        events=[
            ev("Class", mon10, mon10 + h),
            ev("Cancelled", mon10, mon10 + h, status="cancelled"),
            ev("Tomorrow", mon10 + timedelta(days=1), mon10 + timedelta(days=1, hours=1)),
            # 23:30 Sunday local to 00:30 Monday local straddles midnight, so it touches Monday
            ev("Late", NOW - timedelta(hours=9, minutes=30), NOW - timedelta(hours=8, minutes=30)),
            ev(
                "Allday",
                datetime(2026, 11, 16, 5, tzinfo=UTC),
                datetime(2026, 11, 17, 5, tzinfo=UTC),
                all_day=True,
            ),
        ],
    )
    titles = {e["title"] for e in get(app).json()["events"]}
    assert titles == {"Class", "Late", "Allday"}


def test_AC8_10_requires_token(tmp_path):
    app = build(tmp_path, FakeLlm())
    assert TestClient(app).get("/today").status_code == 401


def test_AC8_11_fast_with_cached_explanation(tmp_path):
    app = build(tmp_path, FakeLlm())
    seed(app)
    c = TestClient(app)
    c.get("/today", headers=H)
    t0 = time.perf_counter()
    assert c.get("/today", headers=H).status_code == 200
    assert time.perf_counter() - t0 < 0.3
