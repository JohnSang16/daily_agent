# 05 Obsidian tasks via git

## Purpose
Turn checkbox tasks in my Obsidian vault into shared `tasks`, with due dates, so deadlines I write in notes show up in the ranking.

## Access
1. v1 (local, laptop): the backend reads the vault folder at `OBSIDIAN_VAULT_PATH` directly. Read only.
2. Hosted later: a git checkout with a read only deploy key, as first designed (separate spec).
3. Vault content is untrusted data. The code never executes anything from it, never follows symlinks outside the vault, and rejects paths that escape it.

## Syntax the parser supports
Checkbox lines using `*` or the dash list marker, with `[ ]` for open and `[x]` or `[X]` for done. Metadata tokens follow the title in any order:

```
* [ ] Finish statistics homework 📅 2026-11-20
* [ ] Draft project outline ⏳ 2026-11-18 📅 2026-11-22 [effort:: 90m] [importance:: 4]
* [x] Email advisor 📅 2026-11-10
```

1. Due date: the calendar emoji followed by an ISO date (this matches the popular Obsidian Tasks plugin). Optionally followed by a 24 hour time, which makes the due moment exact instead of date only.
2. Scheduled date: the hourglass emoji. Stored as metadata in v1 and not used for ranking.
3. Effort: `[effort:: 45m]` or `[effort:: 2h]`. Parsed into minutes.
4. Importance: `[importance:: 1]` through `[importance:: 5]`.
5. Priority emojis from the Tasks plugin are ignored in v1.
6. Recurrence markers are ignored. The task is treated as a normal single task.
7. Nested checkboxes are separate tasks. Indented text under a task is ignored.
8. A checkbox with no calendar emoji date is not a task. Undated checklist lines are ignored.
9. Malformed dates (for example `2026-13-45`) leave the task with no due date and `needs_review` true with a reason.

## Scope rules
0. The whole vault is in scope, including `cox/`. Only hidden folders, `node_modules` and `OBSIDIAN_IGNORE_GLOBS` (`templates/*,archive/*`) are skipped.
1. Only `.md` files. Skip hidden folders and anything matching `OBSIDIAN_IGNORE_GLOBS`.
2. File size cap of 1 MB per file and a cap on total files. Oversized files are skipped with a logged count.
3. The fingerprint scope is the relative file path (spec 03).
4. Completed tasks are recorded as `done`.

## Behavior
1. Each sync: walk the vault, parse, upsert, mark missing tasks `gone` (only after a fully successful parse of the whole vault).
2. If the vault path is unreadable, keep old data and record an `error` run.
3. Log only counts and file paths, never task text.

## Acceptance criteria
* AC5.1 The fixture vault parses to the exact expected list of tasks with titles, due dates, effort, and importance.
* AC5.2 Both `*` and dash markers work, and `[X]` counts as done.
* AC5.3 A due date with a time becomes an exact UTC instant. A date alone becomes date only end of day.
* AC5.4 `[effort:: 2h]` yields 120 minutes and `[effort:: 45m]` yields 45.
* AC5.5 A malformed date yields no due date plus `needs_review` with a reason.
* AC5.6 Files under ignored globs and hidden folders are skipped.
* AC5.7 A symlink pointing outside the checkout is not followed.
* AC5.8 A file over the size cap is skipped and counted.
* AC5.9 Editing a task's due date in the vault updates the same task, and editing its title creates a new task and marks the old one `gone`.
* AC5.10 An unreadable vault path leaves existing tasks unchanged and records an error run.
* AC5.11 Two identical task lines in one file stay as two tasks.
* AC5.12 Logs contain no task titles (assert with a log capture).

## Privacy
Tasks under `cox/` reach the LLM as "Cox task" plus the due date, never the real title.
* AC5.13 A `cox/` task title never appears in the LLM prompt (assert on the built prompt).
* AC5.14 A checkbox line with no date yields no task.

## Fixtures
`tests/fixtures/vault/` with several small notes covering every rule above. Build the fixture from synthetic text, not from my real notes.

## Out of scope
Recurring task expansion, the Tasks plugin query syntax, Dataview queries, writing back to notes.

## Open questions
1. Which folders in the vault should be ignored (templates, archive, journal)?
2. Do I already use the Tasks plugin emoji format, or should I start using it?
3. Repository URL and default branch name.
