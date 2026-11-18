import logging
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.db import Base, make_session_factory
from app.llm.explain import build_payload, build_prompt
from app.models import SyncRun, Task
from app.sources.obsidian import sync_obsidian

NY = "America/New_York"
NOW = datetime(2026, 11, 16, 14, 0, tzinfo=UTC)
IGNORE = ("templates/*", "archive/*")


@pytest.fixture
def s():
    sf = make_session_factory("sqlite://")
    Base.metadata.create_all(sf.kw["bind"])
    with sf() as db:
        yield db


def vault(tmp_path, files):
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    return tmp_path


def sync(s, root, **kw):
    return sync_obsidian(s, root, NOW, NY, ignore_globs=IGNORE, **kw)


def tasks(s):
    return list(s.scalars(select(Task).order_by(Task.scope, Task.id)))


def test_AC5_1_exact_list(s, tmp_path):
    root = vault(
        tmp_path,
        {
            "school/stats.md": "# Stats\n* [ ] Finish homework 📅 2026-11-20\n"
            "- [ ] Draft outline ⏳ 2026-11-18 📅 2026-11-22 [effort:: 90m] [importance:: 4]\n",
            "cox/work.md": "- [ ] Ship fix 📅 2026-11-19 14:30\n",
        },
    )
    sync(s, root)
    got = [(t.scope, t.title, t.effort_minutes, t.importance, t.status) for t in tasks(s)]
    assert got == [
        ("cox/work.md", "Ship fix", None, None, "open"),
        ("school/stats.md", "Finish homework", None, None, "open"),
        ("school/stats.md", "Draft outline", 90, 4, "open"),
    ]


def test_AC5_2_markers_and_done(s, tmp_path):
    root = vault(
        tmp_path, {"a.md": "* [x] A 📅 2026-11-20\n- [X] B 📅 2026-11-20\n- [ ] C 📅 2026-11-20\n"}
    )
    sync(s, root)
    assert {t.title: t.status for t in tasks(s)} == {"A": "done", "B": "done", "C": "open"}


def test_AC5_3_due_times(s, tmp_path):
    root = vault(
        tmp_path, {"a.md": "- [ ] Exact 📅 2026-11-20 14:30\n- [ ] Dateonly 📅 2026-11-20\n"}
    )
    sync(s, root)
    by = {t.title: t for t in tasks(s)}
    assert by["Exact"].due_at == datetime(2026, 11, 20, 19, 30, tzinfo=UTC)
    assert not by["Exact"].due_is_date_only
    assert by["Dateonly"].due_at == datetime(2026, 11, 21, 4, 59, 59, tzinfo=UTC)
    assert by["Dateonly"].due_is_date_only


def test_AC5_4_effort(s, tmp_path):
    root = vault(
        tmp_path,
        {"a.md": "- [ ] H 📅 2026-11-20 [effort:: 2h]\n- [ ] M 📅 2026-11-20 [effort:: 45m]\n"},
    )
    sync(s, root)
    assert {t.title: t.effort_minutes for t in tasks(s)} == {"H": 120, "M": 45}


def test_AC5_5_malformed_date_needs_review(s, tmp_path):
    root = vault(tmp_path, {"a.md": "- [ ] Bad 📅 2026-13-45\n"})
    sync(s, root)
    (t,) = tasks(s)
    assert t.due_at is None and t.needs_review and t.review_reason


def test_AC5_6_ignored_paths(s, tmp_path):
    line = "- [ ] X 📅 2026-11-20\n"
    root = vault(
        tmp_path,
        {
            "ok.md": line,
            "templates/t.md": line,
            "archive/o.md": line,
            ".hidden/h.md": line,
            "node_modules/n.md": line,
            "note.txt": line,
        },
    )
    sync(s, root)
    assert [t.scope for t in tasks(s)] == ["ok.md"]


def test_AC5_7_symlink_outside_not_followed(s, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.md").write_text("- [ ] Leak 📅 2026-11-20\n")
    root = tmp_path / "vault"
    vault(root, {"ok.md": "- [ ] Fine 📅 2026-11-20\n"})
    (root / "link.md").symlink_to(outside / "secret.md")
    (root / "linkdir").symlink_to(outside)
    sync(s, root)
    assert [t.title for t in tasks(s)] == ["Fine"]


def test_AC5_8_oversize_skipped_and_counted(s, tmp_path, caplog):
    root = vault(
        tmp_path,
        {"big.md": "- [ ] Big 📅 2026-11-20\n" + "x" * 500, "ok.md": "- [ ] Ok 📅 2026-11-20\n"},
    )
    with caplog.at_level(logging.INFO):
        sync(s, root, max_bytes=200)
    assert [t.title for t in tasks(s)] == ["Ok"]
    assert "skipped_large=1" in caplog.text


def test_AC5_9_edit_due_updates_edit_title_replaces(s, tmp_path):
    root = vault(tmp_path, {"a.md": "- [ ] Essay 📅 2026-11-20\n"})
    sync(s, root)
    first = tasks(s)[0].id
    vault(tmp_path, {"a.md": "- [ ] Essay 📅 2026-11-25\n"})
    sync(s, root)
    (t,) = tasks(s)
    assert t.id == first and t.due_at.day == 26  # end of 25th NY is the 26th UTC
    vault(tmp_path, {"a.md": "- [ ] Essay v2 📅 2026-11-25\n"})
    sync(s, root)
    assert {t.title: t.status for t in tasks(s)} == {"Essay": "gone", "Essay v2": "open"}


def test_deleted_file_marks_tasks_gone(s, tmp_path):
    root = vault(tmp_path, {"a.md": "- [ ] A 📅 2026-11-20\n", "b.md": "- [ ] B 📅 2026-11-20\n"})
    sync(s, root)
    (tmp_path / "b.md").unlink()
    sync(s, root)
    assert {t.title: t.status for t in tasks(s)} == {"A": "open", "B": "gone"}


def test_AC5_10_unreadable_vault_keeps_data(s, tmp_path):
    root = vault(tmp_path / "v", {"a.md": "- [ ] A 📅 2026-11-20\n"})
    sync(s, root)
    with pytest.raises(FileNotFoundError):
        sync(s, tmp_path / "missing")
    assert [t.status for t in tasks(s)] == ["open"]
    assert s.scalars(select(SyncRun).order_by(SyncRun.id.desc())).first().status == "error"


def test_AC5_11_identical_lines_stay_two(s, tmp_path):
    root = vault(tmp_path, {"a.md": "- [ ] Same 📅 2026-11-20\n- [ ] Same 📅 2026-11-20\n"})
    sync(s, root)
    assert len(tasks(s)) == 2


def test_AC5_12_logs_have_no_titles(s, tmp_path, caplog):
    root = vault(tmp_path, {"a.md": "- [ ] TOPSECRETTITLE 📅 2026-11-20\n"})
    with caplog.at_level(logging.DEBUG):
        sync(s, root)
    assert "TOPSECRETTITLE" not in caplog.text


def test_AC5_13_cox_title_never_in_prompt():
    items = [
        {
            "title": "COX-SECRET-TITLE",
            "due_at": "2026-11-20T05:00:00Z",
            "reasons": [],
            "at_risk": False,
            "private": True,
        },
        {
            "title": "Stats homework",
            "due_at": None,
            "reasons": [],
            "at_risk": False,
            "private": False,
        },
    ]
    prompt = build_prompt(build_payload(items))
    assert "COX-SECRET-TITLE" not in prompt and "Cox task" in prompt
    assert "Stats homework" in prompt


def test_AC5_14_undated_checkbox_is_not_a_task(s, tmp_path):
    root = vault(tmp_path, {"a.md": "- [ ] Just a checklist item\n- [ ] Real 📅 2026-11-20\n"})
    sync(s, root)
    assert [t.title for t in tasks(s)] == ["Real"]
