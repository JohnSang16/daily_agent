"""Spec 19: ask extras for the Agent screen (daily full route, courses, course scoped search)."""

from datetime import date, datetime, timedelta

from app.schemas import TaskIn
from app.tasks_sync import sync_tasks
from tests.test_ask import ALL, NOW, FakeLlm, H, ask, build

NY = "America/New_York"
NOTES = {
    "career/school/os-lecture-notes.md": "# Paging\nOperating systems: page tables and the TLB.\n",
    "career/school/physics-lecture-notes.md": "# Circuits\nKirchhoff and page tables, oddly.\n",
    "personal/ideas.md": "# Paging\nPage tables idea for a side project.\n",
}


def due(d):
    return datetime.combine(NOW.date() + timedelta(days=d), datetime.min.time(), NOW.tzinfo)


def seed(app):
    items = [
        TaskIn(
            title="Homework 3 (OPERATING SYSTEMS)", scope="feed", source_ref="feed", due_at=due(3)
        ),
        TaskIn(
            title="Quiz 2 (closes) (OPERATING SYSTEMS)",
            scope="feed",
            source_ref="feed",
            due_at=due(1),
        ),
        TaskIn(title="Lab 4 (PHYSICS)", scope="feed", source_ref="feed", due_at=due(2)),
    ]
    with app.state.session_factory() as db:
        sync_tasks(db, "icollege", "feed", items, NOW, NY)
        sync_tasks(
            db,
            "obsidian",
            "a.md",
            [TaskIn(title="Essay", scope="a.md", source_ref="a:1", due_date=date(2026, 11, 20))],
            NOW,
            NY,
        )


def test_AC19_1_daily_full_is_the_digest(tmp_path):
    llm = FakeLlm()
    app, c, _ = build(tmp_path, NOTES, llm=llm)
    seed(app)
    j = ask(c, "daily full").json()
    assert j["route"] == "digest" and not j["used_llm"] and not llm.prompts
    lines = j["answer"].split("\n")
    assert lines[0].startswith("1. Quiz 2") and len(lines) == 4


def test_AC19_2_courses(tmp_path):
    app, c, _ = build(tmp_path, NOTES)
    seed(app)
    j = c.get("/courses", headers=H).json()
    assert [x["course"] for x in j] == ["OPERATING SYSTEMS", "PHYSICS"]
    assert [a["title"] for a in j[0]["assignments"]] == ["Quiz 2 (closes)", "Homework 3"]


def test_AC19_3_and_4_course_scoped_search(tmp_path):
    llm = FakeLlm()
    app, c, _ = build(tmp_path, NOTES, llm=llm)
    j = c.post(
        "/ask",
        headers=H,
        json={"question": "page tables", "context": ALL, "course": "OPERATING SYSTEMS"},
    ).json()
    paths = [s["path"] for s in j["sources"]]
    assert "personal/ideas.md" not in paths
    assert paths[0] == "career/school/os-lecture-notes.md"


def test_AC19_5_homework_still_needs_tap(tmp_path):
    app, c, _ = build(tmp_path, NOTES, llm=FakeLlm())
    j = c.post(
        "/ask",
        headers=H,
        json={"question": "work on hw 3", "context": ALL, "course": "OPERATING SYSTEMS"},
    ).json()
    assert (
        j["route"] == "homework" and "tap" in j["answer"].lower() and "cover" in j["answer"].lower()
    )


def test_AC19_6_courses_auth(tmp_path):
    app, c, _ = build(tmp_path, NOTES)
    assert c.get("/courses").status_code == 401
