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

### 2026-11-20, spec 13 gate hardening and assignment links
What: the page script now picks the tab on screen (newest first) and follows a click down into frames, so a submit inside an embedded player is judged on the real button. A frame it can't get into is marked opaque and needs approval (fails closed). Quiz and exam detection moved from the browser script into the gate: a timer, proctor or Respondus signal, quiz/exam/midterm in the title or top headings, or a quizzing URL path. Bare "test" no longer refuses ("Test 2 Prepration" is homework). iCollege tasks now keep the item's own link from the feed description in `source_ref` (https iCollege links only, the item page before the calendar link), and "Work on it" opens it directly instead of the iCollege home.
Tests and lint: 309 passed (17 new, the new gate and link tests failed first), ruff clean. Mutation check: turning off the opaque check failed 1 test, turning off the heading check failed 3. Both page scripts pass `node --check`. Real feed: all 20 upcoming items got a link (8 content, 5 dropbox, 5 quizzing, 1 survey, 1 calendar).
Deviation: no migration, the link lives in `source_ref`, which iCollege tasks set to "feed" before. It is not exposed by any endpoint or log.
Not verified: the frame and tab logic only runs in a real browser. Check it on the first real session.
Next step: spec diff for the Gemini solver (a new tool and a new outbound host), then build it.

### 2026-11-20, spec 13 solver (component 7, approved by John)
Spec change (John said yes): boundary 7 now allows a `solve` tool, new component 7 (solver ladder), AC13.17 to AC13.21.
What: `app/agent/solver.py`. The agent's `solve` tool sends only the problem text to a ladder of models (SOLVER_MODELS, default gemini-3.6-flash, gemini-3.8-flash, claude-sonnet-5-5, claude-opus-5-5). An answer comes back only when two rungs agree (numbers within 1 percent, text trimmed and lowercased). Busy or failing rungs are skipped. Each repeat of the same problem in a session starts one rung higher and skips answers marked wrong; the third attempt is refused and the agent asks John. Gemini has its own guarded lane (Interactions API, body limited to model and input). Claude rungs reuse the plain `anthropic` lane (no tools). Solver usage rows (purpose homework_solver) count toward the agent's daily budget.
Acceptance criteria passing: AC13.17 to AC13.21 (14 new tests, all failed first).
Tests and lint: 323 passed, ruff clean.
Live check: gemini-3.6-flash answered a real physics problem correctly (4500 N). gemini-3.8-flash returned 503 (busy). Both Claude rungs returned 401: the ANTHROPIC_API_KEY in .env is invalid, which also blocks the agent itself. John needs a new key.
Open: the solver is text only, diagrams are not sent yet. Answer entry checks (spec step 4) wait for the first real session, they depend on Pearson's real inputs.
Next step: new Anthropic key, then the first real session.

### 2026-11-20, spec 13 diagrams, read back and review report (John: "can't you do this now")
What: `solve` takes `diagram: true` and sends the current screenshot to every rung as a PNG (Gemini lane allows inline text and PNG blocks only). After typing into a plain field the agent is told if the field doesn't hold what it typed (password fields never read). The system prompt says to ctrl+a before typing an answer. `GET /agent/report?days=3` ranks what went wrong (gate pauses, limits, blocks, questions, stops, solves that didn't agree). Solver replies are judged on the final line, the last bold part or what follows the last "=", because Sonnet shows working even when told not to.
Acceptance criteria passing: AC13.22 to AC13.24 (all failed first), plus the answer line parsing tests.
Tests and lint: 337 passed, ruff clean, page script passes `node --check`.
Live: Gemini 3.6 Flash and Claude Sonnet agree on a car force problem (4500 N) and on a drawn circuit diagram (2 A).
Merged: feat/cli-llm-backend (the text only Claude CLI backend). Do not set LLM_BACKEND=cli on the Cox Mac: its claude login is the Cox enterprise account.
Not done: sign in push (needs APNs and a notifications spec, principles list it as later). Pearson specific answer entry (equation editor, units, drag and drop) waits for the first real session.
Next step: first real session on a practice assignment, then record AC13.16 cost.

## 2026-11-21 Gmail OA sweep (spec 15, first cut)
Direct Gmail client on the calendar's token file, one no tools extraction call per new invite, processed ids in `gmail_seen` (migration 0010). Undated invites lead the digest as "no deadline given". AC15.21 to AC15.27. The host Mac needs `scripts/google_auth.py` rerun so its token carries the gmail scope.

## 2026-11-23 ask anything, homework agent on Sonnet (specs 13 and 14, approved by John)
What: ask answers any question. Notes that match are used and cited; when none match or the vault is off, the question goes to the model on its own (route `general`, no note text in the prompt, same budget and usage row). The homework agent now runs on claude-sonnet-5-5 (`AGENT_MODEL`) and moves to `AGENT_ESCALATE_MODEL` (claude-opus-5-5) for the rest of a session after a failed, cut off or declined step.
Acceptance criteria passing: AC14.3 and AC14.13 (rewritten), AC14.16, AC13.25 (all failed first).
Tests and lint: 351 passed, ruff clean.
Still blocked: the ANTHROPIC_API_KEY in .env was invalid on 2026-11-20, so no live check. Billing is Console credits (LLM_BACKEND=api); do not use the cli backend on the Cox Mac.

## 2026-11-23 money overview redesign
What: Money overview now has a trend hero card (day/month toggle, spend only line chart, income and net in a footer line, above/below average line), a category donut (top 5 plus other) and ring gauge budget goals. `GET /money/summary` gained `daily`, a running total of this month's spend through today, using the same rules as month_totals. Spec: docs/superpowers/specs/2026-11-23-money-overview-redesign-design.md.
Tests and lint: 362 passed, ruff clean on touched files (5 E501 in tests/test_backend_additions.py and tests/test_homework_agent.py were already there). iOS typecheck passed, Checks/main.swift all passed.
Deviations: average line checks use dollar scale cents (the plan's fixtures were 100x too small for "$150"). `Bar` kept, DashboardView still uses it. One Chart with conditional axes instead of two copies. Ring trim capped at 100 percent.
Next step: run on the phone and check the hero toggle, donut and rings at real data sizes.

## 2026-11-23 money tabs: banks and activity redesign, income tab removed
What: banks has a net worth card with a share bar and glass bank cards. Activity has search, filter chips (all, spending, income, pending), category symbols and per day net totals, all filtered client side over the loaded page (latest 100). Income tab, its 500 row fetch and incomeByMonth removed. iOS only, no backend change.
Tests: iOS typecheck passed, Checks/main.swift all passed (new checks for holdingShares, dollarsAndCents, netCents, filterTxns, categoryIcon).
Open: search and the income filter only cover the loaded 100 rows. A backend `q` param is the upgrade if older history matters.
Next step: run on the phone.

## 2026-11-23 activity: spend calendar and recurring
What: activity replaces the search field with a spend calendar (from summary.daily, tap a day to filter) and a small recurring row. New `GET /money/recurring`: a merchant charged in 2 or more months of the last 100 days, about once a month, each charge within 20 percent of the middle amount; transfers, card payments and income never count. Next date is the last charge plus one month (monthly bills only).
Tests and lint: 364 passed (2 new recurring tests, failed first), ruff clean on touched files. iOS typecheck passed, Checks/main.swift all passed.
Next step: run on the phone, check recurring against real Plaid data for false positives.

## 2026-11-25 money goals tab (spec 16, approved by John)
What: `savings_goals` table (migration 0011) and `GET/PUT/DELETE /money/goals` (`/goals` was taken by spec 18). Goal kinds: one account's balance, net worth, invested, cards owed, and one `income_since` stretch goal with a floor. iOS: a goals tab in Money (stretch, budget columns, season switch) and a stretch card on the dashboard that jumps to it. `scripts/seed_money_goals.py` loads John's goals ($606k stretch from 2026-11-25, floor $100k, three seasons) and budgets (food $205, gas $120, shopping $60), found by account last four.
Acceptance criteria passing: AC16.16 to AC16.19 (all failed first).
Tests and lint: 358 passed, ruff clean, iOS typecheck passed (no Xcode on this Mac, not run on a device).
Found: bank_accounts has the three Marcus accounts twice (ids 3 to 5 and 9 to 11), so savings and net worth count them double. Turn the second set off in the banks sheet.
Next step: on the host Mac, `uv run alembic upgrade head`, then `uv run python -m scripts.seed_money_goals`, then build the app.
Done same day: duplicate Marcus login removed with `DELETE /banks/6` (Plaid item removed too). Backup before the change: `~/projects/daily_agent-backups/dev-before-marcus-dedupe-20261125.sqlite3`.
