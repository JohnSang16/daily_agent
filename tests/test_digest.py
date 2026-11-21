from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient

from app.clock import FixedClock, get_clock
from app.config import Settings
from app.db import Base
from app.digest import read_lines, read_why
from app.main import create_app
from app.models import SyncRun
from app.schemas import TaskIn
from app.tasks_sync import sync_tasks

NY = "America/New_York"
NOW = datetime(2026, 11, 19, 21, 0, tzinfo=UTC)
H = {"Authorization": "Bearer tok"}


def build(tmp_path, files=None, **kw):
    vault = tmp_path / "vault"
    for rel, text in (files or {}).items():
        p = vault / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    vault.mkdir(exist_ok=True)
    s = Settings(
        _env_file=None,
        api_token="tok",
        database_url=f"sqlite:///{tmp_path}/t.db",
        obsidian_vault_path=str(vault),
        **kw,
    )
    app = create_app(s, sources={})
    Base.metadata.create_all(app.state.session_factory.kw["bind"])
    app.dependency_overrides[get_clock] = lambda: FixedClock(NOW)
    return app, TestClient(app)


def add(app, titles_days):
    with app.state.session_factory() as db:
        sync_tasks(
            db,
            "obsidian",
            "a.md",
            [
                TaskIn(title=t, scope="a.md", source_ref=t, due_date=d)
                if d
                else TaskIn(title=t, scope="a.md", source_ref=t)
                for t, d in titles_days
            ],
            NOW,
            NY,
        )


def test_deadlines_capped_at_seven_with_overflow_and_no_undated(tmp_path):
    app, c = build(tmp_path)
    add(
        app,
        [(f"T{i}", date(2026, 11, 20) + timedelta(days=i)) for i in range(10)]
        + [("No date", None)],
    )
    j = c.get("/digest", headers=H).json()
    assert len(j["deadlines"]) == 7 and j["overflow"] == 3
    assert [d["title"] for d in j["deadlines"]] == [f"T{i}" for i in range(7)]  # nearest first
    assert all(d["due_local"] for d in j["deadlines"]) and "No date" not in str(j)


def test_nothing_due_is_an_empty_list_not_filler(tmp_path):
    app, c = build(tmp_path)
    add(app, [("No date", None)])
    j = c.get("/digest", headers=H).json()
    assert j["deadlines"] == [] and j["overflow"] == 0


def test_old_overdue_is_not_in_the_brief(tmp_path):
    app, c = build(tmp_path)
    add(app, [("LEETCODE", date(2026, 5, 24)), ("Essay", date(2026, 11, 25))])
    j = c.get("/digest", headers=H).json()
    assert [d["title"] for d in j["deadlines"]] == ["Essay"]
    assert any("hidden" in n for n in j["notes"])


def test_mantra_vision_and_why_come_from_the_vault(tmp_path):
    lines = "# Digest lines\n\nMANTRA: Stay delusional. Keep pushing.\nVISION: FAANG next summer.\n"
    reflections = (
        "# Reflections\n\nRelated: x\n\n---\n\n"
        "## 2026-11-18\n\nI want it because my parents sacrificed.\n\n"
        "## 2026-11-19\n\nBecause I am tired of almost.\n"
    )
    files = {"_meta/digest-lines.md": lines, "personal/reflections.md": reflections}
    app, c = build(tmp_path, files)
    j = c.get("/digest", headers=H).json()
    assert j["mantra"] == "Stay delusional. Keep pushing." and j["vision"] == "FAANG next summer."
    assert j["why"] == {"date": "2026-11-19", "text": "Because I am tired of almost."}


def test_missing_vault_files_just_leave_those_fields_empty(tmp_path):
    app, c = build(tmp_path)
    j = c.get("/digest", headers=H).json()
    assert j["mantra"] is None and j["vision"] is None and j["why"] is None


def test_empty_reflections_has_no_why(tmp_path):
    assert read_why("# Reflections\n\nRelated: x\n\n---\n") is None
    assert read_lines("") == {}


def test_stale_source_shows_as_a_quiet_note(tmp_path):
    app, c = build(tmp_path)
    t = NOW - timedelta(hours=9)
    with app.state.session_factory() as db:
        db.add(SyncRun(source="google_calendar", started_at=t, finished_at=t, status="ok"))
        db.commit()
    j = c.get("/digest", headers=H).json()
    assert any("google calendar" in n and "out of date" in n for n in j["notes"])


def test_digest_needs_the_token(tmp_path):
    app, c = build(tmp_path)
    assert c.get("/digest").status_code == 401


def test_identity_lines_come_from_the_vault_in_order(tmp_path):
    lines = (
        "MANTRA: Keep pushing.\n"
        "IDENTITY: I'm a Googler.\nIDENTITY: I put in the reps.\nIDENTITY: Fear is not real.\n"
    )
    app, c = build(tmp_path, {"_meta/digest-lines.md": lines})
    j = c.get("/digest", headers=H).json()
    assert j["identity"] == ["I'm a Googler.", "I put in the reps.", "Fear is not real."]
    assert j["mantra"] == "Keep pushing."


def test_identity_is_empty_when_the_file_is_missing(tmp_path):
    app, c = build(tmp_path)
    assert c.get("/digest", headers=H).json()["identity"] == []


PLAN = (
    "# Today's plan\n\nOverwritten each day.\n\n"
    "## 2026-11-19\n\n- [ ] Workout at the climbing gym\n- [x] Do the lab (2 pm)\n"
)


def test_todays_plan_is_read_when_it_is_dated_today(tmp_path):
    app, c = build(tmp_path, {"personal/today-plan.md": PLAN})
    plan = c.get("/digest", headers=H).json()["plan"]
    assert plan["logged"] is True
    assert plan["items"] == [
        {"text": "Workout at the climbing gym", "done": False},
        {"text": "Do the lab (2 pm)", "done": True},
    ]


def test_a_plan_from_another_day_counts_as_not_logged(tmp_path):
    app, c = build(tmp_path, {"personal/today-plan.md": PLAN.replace("2026-11-19", "2026-11-18")})
    plan = c.get("/digest", headers=H).json()["plan"]
    assert plan == {"logged": False, "items": []}


def test_overflow_names_the_date_it_runs_past(tmp_path):
    app, c = build(tmp_path)
    add(app, [(f"T{i}", date(2026, 11, 20) + timedelta(days=i)) for i in range(10)])
    j = c.get("/digest", headers=H).json()
    assert j["overflow"] == 3 and j["overflow_after"] == "Thu Nov 26"  # the 7th deadline's day


def test_ac15_23_undated_oa_invite_goes_first(tmp_path):
    app, c = build(tmp_path)
    add(app, [(f"T{i}", date(2026, 11, 20) + timedelta(days=i)) for i in range(8)])
    with app.state.session_factory() as db:
        oa = TaskIn(
            title="Beta online assessment",
            scope="msg:m1",
            source_ref="https://mail.google.com/mail/u/0/#all/m1",
            needs_review=True,
            review_reason="no deadline given",
        )
        sync_tasks(db, "gmail", "msg:m1", [oa], NOW, NY)
    j = c.get("/digest", headers=H).json()
    first = j["deadlines"][0]
    assert first["title"] == "Beta online assessment" and first["due_local"] == "no deadline given"
    assert len(j["deadlines"]) == 7 and j["overflow"] == 2
