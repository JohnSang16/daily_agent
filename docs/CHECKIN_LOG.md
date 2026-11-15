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

### 2026-11-15, spec 17 write protection
Acceptance criteria passing: AC17.1 to AC17.8, AC17.10, AC17.11. AC17.9 partial (no source code exists yet to inject into; strengthen in specs 05 and 06). AC17.12 and AC17.13 deferred to spec 10.
Tests and lint: 35 passed; ruff clean. Mutation check: dropping the method check fails 7 tests.
Deviations: implementation was written before the tests (process slip), then verified by the mutation check. httpx moved from dev to runtime dependency. Built on Sonnet, not the strongest model: needs a strongest-model review.
Found by tests: httpx's own logger wrote full URLs with query strings at INFO. Silenced httpx/httpcore loggers.
Open questions: host firewall rule; browser-level submit blocking (spec 13).
Next step: strongest-model review of spec 17, then spec 03.
