# Check in log

Newest entries at the bottom. Claude Code appends an entry at the end of every task.

## Entry template
Date:
Spec and task:
Acceptance criteria passing:
Tests and lint:
Deviations:
Open questions:
Next step:

## Log
No entries yet. Project created from the planning conversation.

### 2026-11-15, spec 02 skeleton
Acceptance criteria passing: AC2.1 to AC2.7, AC2.9 (AC2.8 holds locally)
Tests and lint: 8 passed; ruff clean
Deviations: no GitHub Actions (John: solo project). Version is `app.__version__` (no build backend, avoids a new dependency). Alembic env reads DATABASE_URL via Settings.
Open questions: none for 02.
Next step: spec 17 write protection (needs the strongest model).
