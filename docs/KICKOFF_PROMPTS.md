# Kickoff prompts for Claude Code

Paste these in order. Replace the bracketed parts. Prompts are written so Claude Code stays inside the specs, shows a plan before coding, and reports in the same format every time.

## Prompt 0: first session, project orientation
```
Read CLAUDE.md, specs/00_principles.md, and specs/01_overview.md. Then read docs/SETUP_CHECKLIST.md.
Do not write any code yet. Reply with:
1. A five sentence summary of the project in your own words.
2. Any contradictions or gaps you notice across the specs.
3. The Open questions you need me to answer before spec 02.
Then wait for me.
```

## Which model for which spec
Rule of thumb: if the work touches secrets, permissions, approvals, untrusted text, or money, use your strongest model. Everything else can use a faster, cheaper one, because the tests catch mistakes. Check which models your plan allows and how quickly the strongest one uses your allowance, since cloud sessions share limits with your other Claude Code use. Pick the model per session.

1. Planning and answering a spec's open questions: strongest.
2. Spec 02 skeleton: fast.
3. Spec 17 write protection: strongest.
4. Spec 03 shared model: fast. Read the daylight saving tests yourself.
5. Spec 04 Google Calendar: fast, then ask the strongest model to review the sign in and token handling.
6. Spec 05 Obsidian: fast, then a strongest model review of the path and symlink checks.
7. Spec 06 Gmail digest: strongest (prompt injection safety).
8. Spec 07 priority engine: fast.
9. Spec 08 today endpoint: fast.
10. Spec 09 sync jobs and deployment: fast, then Prompt 6 (the security review) on the strongest model.
11. Spec 10 iPhone app: fast for screens, strongest for anything about the Keychain, the token, and networking.
12. Spec 13 homework browser agent: strongest, especially the approval gate.
13. Spec 14 ask your vault: fast for search, strongest for the context enforcement on the backend.
14. Spec 15 connectors and digest: strongest.
15. Spec 16 money list: strongest.
16. Any security review (Prompt 6) and any check in review of risky code: strongest.

A good habit: let a fast model build, then open a new session on the strongest model and use the check in report prompt (Prompt 2) or the security review prompt (Prompt 6) to review the result without changing files.

## Prompt 1: the reusable build prompt (use for specs 02 through 09)
```
We are working on spec [NUMBER AND NAME], in specs/[FILE].
Follow CLAUDE.md. Use the Superpowers workflow with these limits:
1. Brainstorm only the Open questions in that spec. Ask me one at a time. Do not re ask settled decisions.
2. Then write the implementation plan as a short numbered list of small tasks, each tied to acceptance criteria IDs, and list every new dependency with a one sentence reason.
3. STOP and wait for my explicit yes before writing code.
After I say yes:
4. Create the branch [BRANCH NAME].
5. Write the failing tests first and show me the failing output.
6. Implement the smallest code that passes. Execute inline in this session, no subagents.
7. Run uv run pytest and uv run ruff check . and show the summary lines.
8. Do not commit until I say so.
9. Finish with the end of task report format from CLAUDE.md and append a check in log entry.
```

## Per spec notes: what to have ready before you paste Prompt 1

### Spec 02 skeleton
1. Branch `spec02_skeleton`.
2. Decide: optional GitHub Actions workflow, and the secret scanner for pre commit.

### Spec 17 write protection (do this right after spec 02)
1. Branch `spec17_write_protection`.
2. Tell Claude Code to build the guarded HTTP client, the scope allowlist test, the static write check, and the audit log first, with tests, before any integration.
3. Reminder: the strongest layer is read only credentials at the provider, so every later connection must use read only scopes and a read only deploy key.
4. After each integration is connected, do the manual check in the spec: try one harmless write with the stored token and confirm the provider refuses it.

### Spec 03 shared model
1. Branch `spec03_model`.
2. Nothing to bring. Ask Claude to pay special attention to the daylight saving tests.

### Spec 04 Google Calendar
1. Branch `spec04_google_calendar`.
2. Have your Google Cloud project, OAuth client file in `secrets/`, and the list of calendar ids ready (setup checklist section 4).
3. Decide Testing versus production consent screen status after Claude summarizes current Google documentation on refresh token expiry.
4. Manual step at the end: run the auth script yourself and confirm real events in `/today`.

### Spec 05 Obsidian
1. Branch `spec05_obsidian`.
2. Have the vault repository URL, a read only deploy key set up, and your ignore folder list.
3. Tell Claude to build the fixture vault from synthetic notes only.

### Spec 06 Gmail digest
1. Branch `spec06_gmail_digest`.
2. Have the sender address or search query and a redacted real sample of one digest saved in `tests/fixtures/digests/`.
3. Have an Anthropic API key with a monthly spending limit set in the console. Tests must not use it.

### Spec 07 priority engine
1. Branch `spec07_priority`.
2. Answer: same working hours every day, or per weekday windows?
3. No external services. This spec should be the fastest.

### Spec 08 today endpoint
1. Branch `spec08_today`.
2. Decide whether `/today` includes a preview of tomorrow's top three.

### Spec 09 scheduled syncs and deploy
1. Branch `spec09_sync_deploy`.
2. Choose the host and cron mechanism first. Ask Claude to compare two options briefly and wait for your choice.
3. Manual step at the end: deploy and verify `/health` and `/today` over HTTPS.

### Spec 10 iOS app
1. Branch `spec10_ios`. Needs a Mac.
2. Tell Claude Code to open `design/prototype.html` and `design/DESIGN_NOTES.md` first and match them.
3. Ask for the backend additions (reminders upload, snooze, done) as their own small plan before any Swift code.

### Spec 15 connectors and digest
1. Branch `spec15_connectors_digest`.
2. Before the plan, tell Claude Code to read `.claude/commands/daily-full.md` from your vault checkout and treat it as the digest's source of truth, as described in the spec. Also fix the numbering issue in the command (identity list and deadline list share numbers).
3. Ask Claude Code to read the current documentation for MCP connection from a backend, tool allowlists, and OAuth handling, and summarize the options before choosing.
4. Tell it the allowlist and the write tool blocking are built and tested first, before any digest logic.
5. Manual check at the end: connect Gmail, confirm send is shown as blocked, build a digest, and compare it with what `/daily full` gives you in the vault.

### Spec 16 money list
1. Branch `spec16_money`. Do not connect real bank accounts until the security checks in the spec pass.
2. Before the plan, ask Claude Code to read the current pricing and terms of two bank data aggregators for one personal user and summarize them, then wait for your choice.
3. Tell it to build the read only permission check and the token encryption first, with tests, before any bank sync code.
4. Manual check at the end: connect one account, confirm transactions show with the right bank, and confirm no payment permission was requested.

### Spec 14 ask your vault
1. Branch `spec14_vault_query`. You can start it right after spec 05, before the app exists.
2. Decide which folders or tags are private and excluded.
3. Remind Claude Code there is no separate vault mode: ask handles notes through a per chat context setting that the backend enforces.
4. Tell Claude Code to start with keyword search and only propose embeddings if it can show keyword search is not enough.
5. Manual check at the end: ask five real questions and confirm each answer shows its source note.

### Spec 13 homework browser agent
1. Branch `spec13_browser_agent`. Do not start until the gate in the spec is met.
2. Before the plan, ask Claude Code to read the current Kernel documentation on live view, browser profiles, and managed login, and summarize it for you.
3. Ask for a cost estimate for one session before building.
4. Tell it the approval gate is the first thing built and tested, before any agent loop.
5. Manual steps at the end: sign in yourself through the live view and run one harmless practice assignment.

## Prompt 2: check in report (use before every check in with me)
```
Prepare my check in report. Read docs/CHECKIN_LOG.md and the current spec.
Output exactly:
1. Current spec and branch.
2. Each acceptance criterion ID with PASS, FAIL, or NOT STARTED.
3. Summary lines of uv run pytest and uv run ruff check .
4. What changed since the last check in (files and one line each).
5. Anything that deviates from the spec.
6. Blockers and questions for me.
7. Your recommended next step.
Do not change any files.
```

## Prompt 3: change a spec on purpose
```
I want to change [SPEC FILE] because [REASON]. Propose the change as a diff only. List which acceptance criteria and tests would change. Do not edit any file until I approve.
```

## Prompt 4: something is failing and I do not understand why
```
Tests are failing in [AREA]. Do not guess. Reproduce it, read the failure carefully, and state the root cause with evidence before proposing a fix. Make the smallest change that fixes the cause. Do not weaken or delete a test unless the spec was wrong, and if so, tell me first.
```

## Prompt 5: resume after a break
```
Read CLAUDE.md and docs/CHECKIN_LOG.md. Summarize where we stopped, what is on the current branch, and what the next small step is. Check git status and report anything uncommitted. Do not change anything.
```

## Prompt 6: security review before deploying (end of spec 09)
```
Do a read only security review of this repo against the Security baseline in specs/00_principles.md.
Check: auth on every route except health, secrets in the repo or git history, logging of private text, token encryption, dependency pinning, untrusted input handling in the email and vault code paths, and read only scopes everywhere.
Report findings by severity with file and line references. Do not change files.
```

## Rules for yourself while using these prompts
1. Keep permission prompts on in Claude Code. Do not use any mode that skips approvals.
2. Never paste real secrets into the chat. Use the env file.
3. If Claude Code proposes something that touches Cox data, stop and read spec 11.
4. Commit only after you have read the diff.
