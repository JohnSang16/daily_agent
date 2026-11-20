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

### 2026-11-15, spec 03 shared model
Acceptance criteria passing: AC3.1 to AC3.9 (migration verified with real alembic upgrade).
Tests and lint: 52 passed; ruff clean.
Deviations: added a `scope` column on tasks (spec needs "source scope" for gone-marking but lists no column). Importance: a source only sets it when no value exists, so a local override survives. OutboundCall (spec 17) now uses integer user_id and the tz-aware UTC type to match this spec. Tests written first, shown failing at import.
Open questions: none.
Next step: spec 07 priority engine.

### 2026-11-15, spec 07 priority engine
Acceptance criteria passing: AC7.1 to AC7.14.
Tests and lint: 73 passed; ruff clean. Mutation checks: loosening at-risk fails tests; flipping importance order fails tests.
Deviations: none. Open questions answered by default, change if wrong: same working hours every day, 09:00 to 17:00 (Config.work_start/work_end); tentative events block time. `suggested_block` returns the whole free block, not a trimmed slot.
Next step: spec 08 /today endpoint.

### 2026-11-15, spec 08 today endpoint
Acceptance criteria passing: AC8.1 to AC8.11.
Tests and lint: 88 passed; ruff clean. Mutation checks: disabling the cache fails 3 tests; disabling the contradiction guard fails 1.
Deviations: no real LLM client yet (needs your Anthropic key and spec 06). `create_app(settings, llm=None)` takes any client with `complete(prompt)`; with none, the explanation is the template. `date` only changes the events day and the response date, ranking always uses the real now. Budget is per local day via LLM_DAILY_TOKEN_BUDGET (default 20000). Settings gained work_start, work_end, default_effort_minutes, llm_model, stale_after_hours.
Open question answered by default: no tomorrow preview (the response shape in the spec has none). Say if you want it.
Next step: end-to-end test, then spec 04 needs your Google OAuth.

### 2026-11-19, iOS UX pass and triage
What: a frontend bug and polish pass over every screen of the app, plus a read only backend bug review. Full list in docs/TRIAGE.md.
Checks: `ios/DailyAgent/Checks/typecheck.sh` (new: typechecks every SwiftUI screen without Xcode, also clean at a macOS 14 target, which roughly matches iOS 17), logic checks all passed (5 new). Backend: 223 passed, ruff clean, no backend code changed.
Deviations: none from specs. Bank names keep their case (design notes: proper names are not lowercased).
Open questions: backend bugs 5 and 6 in TRIAGE.md need spec wording changes (transfers, overdue iCollege items).
Next step: fix backend bugs 1 to 3, then run the app on the phone once.

### 2026-11-19, backend triage fixes
What: fixed all 14 bugs in docs/TRIAGE.md, plus the vault checkout deploy key path (a relative path broke every fetch after the first clone).
Tests and lint: 244 passed (21 new in tests/test_triage_fixes.py, each failed first), ruff clean. iOS typecheck clean.
Spec changes (asked for by "fix all the backend bugs"): spec 06 keeps missed iCollege items 14 days, spec 08 limit max 500, spec 16 cash withdrawals count as spending.
Open: Venmo or Zelle payments to other people still read as transfers. Plaid gives no reliable way to tell them apart from moves between your own accounts. Duplicate Marcus (bank id 6) still needs DELETE /banks/6.
Next step: run the app on the phone, then the week endpoint.

### 2026-11-20, spec 18 goal follow through
Acceptance criteria passing: AC18.1 to AC18.11 (19 tests, written first, failed at import).
Tests and lint: 263 passed, ruff clean. Migration 0008 runs up and down on a scratch database. iOS typecheck clean at macOS 26 and 14, logic checks pass (13 new).
Deviations: none. The widget is out of scope on purpose (see spec 18, it needs a call on App Groups or where the token is stored).
Open questions: widget. Also suggested: make the identity lines process based ("I'm the type of person that ...") instead of outcome based ("I'm a Googler"). That is John's call, in `_meta/digest-lines.md`.
Next step: `uv run alembic upgrade head` on the agent Mac, restart the agent, then run the app.

### 2026-11-20, spec 19 agent screen (ask and homework study helper)
Acceptance criteria passing: AC19.1 to AC19.6 (written first, all 5 failed for the right reason).
Tests and lint: 268 passed, ruff clean. iOS typecheck clean at macOS 26 and 14, logic checks pass (5 new). The Xcode project was regenerated with xcodegen: the only changes are AgentView.swift plus the microphone and speech usage strings.
Deviations: email context stays off (spec 06 isn't built). The homework mode is a study helper on purpose (John's pick). Spec 13 stays gated.
Next step: run on the phone and try dictation (it needs on device recognition, which is iOS 17 or later on recent iPhones).

### 2026-11-20, spec 13 homework browser agent
Gate, in John's words (2026-11-20):
- College AI policy: "yea its allowed". AI help on homework is allowed. Recorded as John's statement. He is responsible for following each course's syllabus.
- Pearson terms: "Pearson fully, I accept it". Pearson is on the allowlist with the same approval rules as iCollege.
- Gate 1 (`/today` trustworthy for a week): waived by John, the same way as the iOS gate.
- Gate 2 (live view in the app): built in this change (HomeworkSessionView).
Still out of scope per the spec, whatever the policy says: exams, quizzes, timed work, auto submit. The gate refuses those pages.
Acceptance criteria passing: AC13.1 to AC13.15 (24 tests in tests/test_homework_agent.py). AC13.16 (average cost of one session) is still open: measure it on the first real session from `agent_sessions.input_tokens/output_tokens`.
Tests and lint: 292 passed, ruff clean. Migration 0009 runs up and down. iOS typecheck clean at macOS 26 and 14.
Deviation: the code was written before its tests. To prove the tests bite, I broke the gate on purpose: removing the submit check failed 7 tests, removing the allowlist check failed 2, and making approvals reusable failed 1.
Live check against real Kernel: started a browser, took a screenshot, read the page on gastate.view.usg.edu, then deleted the browser. No Claude call and no sign in.
Open questions answered:
1. Profiles: a "school" profile with save_changes, so you sign in once in the live view and later sessions reuse it. Kernel's managed auth is not used.
2. Two step sign in: not tested yet. The gate pauses on any page outside the allowed sites, so you sign in yourself.
4. Blocking submissions at the network level as a second safety net: not done. Kernel's Playwright execution is per call, so a route block would not persist reliably. The gate checks the real element under every click, and pressing Enter inside a form needs approval.
5. Driver: screenshots for the model, plus a fixed page script that reads the real element under each click for the gate.
6. Cost: see AC13.16.
Model: claude-opus-5-5 at effort medium, with server side refusal fallbacks (`fallbacks: "default"`). AGENT_MODEL and AGENT_EFFORT change it.
