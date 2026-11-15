# 01 Overview and architecture

## Goal
One endpoint, `GET /today`, that returns my top priority task, my ranked tasks, today's schedule, and a short plain language explanation. (The API may also return free blocks for the priority engine and for choosing a suggested start time, but the app does not display free time.) It is built from three sources: Google Calendar, Obsidian task notes, and a college email digest in Gmail.

The app is called js ai. It has a calendar view that shows my events and tasks together, one agent page with modes (ask and homework) where I can ask anything or work on homework, and a daily digest built from my email through connectors (spec 15). Questions about my Obsidian notes are answered in ask through a context picker (spec 14).

A second goal comes after that works: a homework agent that works in a cloud browser on my iCollege and Pearson assignments while I watch live on my phone, and that must get my approval before anything is submitted (spec 13).

## User story
As John, every morning I want to see the one thing I should do first, based on nearest deadline, so I stop deciding and start working.

## Data flow
```
Google Calendar ===> sync ===\
Obsidian git repo ==> sync ====> database ===> priority engine ===> /today ===> (later) iOS app
Gmail digest ==> sync + LLM ==/                                  \=> explanation (LLM, cached)
```

## Components
1. **Sources** (`app/sources/`): one module per source. Each exposes a `sync()` that fetches, normalizes into the shared model (spec 03), and upserts. Each wraps its external API in a small client interface so tests use fakes.
2. **LLM layer** (`app/llm/`): a client wrapper with budget tracking, an extraction function for email digests (spec 06), and an explanation function (spec 08).
3. **Priority engine** (`app/priority/`): a pure function. No database, no network, no clock calls. Everything is passed in.
4. **API** (`app/api/`): `health`, `today`, `sync`, `ask`. Bearer auth on everything but health.
   **Ask** (`app/ask/`, spec 14): note indexing, search, a small router, and answers with sources.
   **Connectors and digest** (`app/connectors/`, `app/digest/`, spec 15): an MCP gateway with per connector read only allowlists, and the daily digest builder.
5. **Jobs** (`app/jobs/`): the sync runner, locks, and run history (spec 09).
6. **Core**: `config.py`, `auth.py`, `db.py`, `models.py`, `clock.py`.
7. **Browser agent** (`app/agent/`, spec 13): session manager for Kernel cloud browsers, the agent loop, and the approval gate that blocks submit, send, and pay actions until I approve. The phone shows the browser through Kernel's live view.

## Module layout
```
app/
  main.py
  config.py
  auth.py
  clock.py
  db.py
  models.py
  schemas.py
  sources/
    base.py
    google_calendar.py
    obsidian.py
    gmail_digest.py
  llm/
    client.py
    extraction.py
    explain.py
  priority/
    engine.py
  api/
    health.py
    today.py
    sync.py
  jobs/
    runner.py
tests/
  fixtures/
  test_*.py
scripts/
  google_auth.py
```

## Build order and pacing
Sessions are small. Each spec lists acceptance criteria. Suggested order:
1. Spec 02 skeleton.
2. Spec 17 write protection: the guarded HTTP client and the read only scope allowlist, before any integration.
3. Spec 03 shared model.
4. Spec 04 Google Calendar. First milestone: `/today` shows real events.
5. Spec 05 Obsidian tasks.
6. Spec 06 Gmail digest.
7. Spec 07 priority engine.
8. Spec 08 today endpoint with explanation.
9. Spec 09 scheduled syncs and deployment.
10. Spec 10 iOS app (needs a Mac). The design prototype in `design/` defines the look and navigation.
11. Spec 15 connectors and digest. It reads my `/daily full` command from the vault checkout, so it comes after spec 05.
12. Spec 16 money list (needs a security review before real accounts are connected).
13. Spec 14 ask your vault. It can start as soon as spec 05 is done, even before the app exists, because `POST /ask` is testable on its own.
14. Spec 13 homework browser agent, after the app can show the live view.
15. Specs 11 and 12 only when their gates open.

Check in with Claude every few days using `docs/CHECKIN_TEMPLATE.md`.

## Known risks
1. **Google OAuth in Testing mode.** For apps left in Testing status, Google may expire refresh tokens after about 7 days, which would make the Google syncs fail weekly. Mitigation is in spec 04. Verify against current Google documentation before relying on it.
2. **Gmail digest format drift.** The college email may change layout. Extraction must be tolerant and flag low confidence (spec 06).
3. **Prompt injection through email.** Covered by principle 3 and spec 06.
4. **Work account policy.** Outlook is a Cox work account. See spec 11. No Cox data enters this project until IT approves in writing.
5. **LLM cost drift.** Budget and caching rules in specs 06 and 08. The browser agent will cost far more per task than everything else, so spec 13 requires measuring it before committing to the ten dollar target.
6. **Academic integrity.** My college may restrict AI help on assignments. I am responsible for checking its policy. The agent never submits without my approval, and by default never works on timed, proctored, or exam style assessments (spec 13).
7. **Website terms and bot detection.** Pearson or the school may prohibit automated access or block it. The agent never bypasses CAPTCHAs or bot checks. It hands the browser to me instead.
8. **Hostile web content.** A web page can contain text aimed at the agent. Spec 13 treats pages as untrusted and enforces limits in code.

## Decision log
1. Nearest deadline first is the ranking rule (decided by John).
2. Voice is deferred until the rest works (decided by John).
3. Backend language is Python (decided by John).
4. Obsidian vault syncs through a git repo (confirmed by John).
5. Tasks also live in Apple Reminders, which has no cloud API, so Reminders arrive with the iOS app (spec 10).
6. Homework agent mode: it works in the browser and I approve before any submit (decided by John).
7. Platforms: Pearson and iCollege (decided by John).
8. App design: mobile first, dark mode only, sleek, simple, and understated, like a personal Jarvis. A slide out side drawer, a Home and Agent switch at the top, and a command bar at the bottom. No separate task cards and no Next up section: just a simple list, then the schedule (decided by John). The prototype in `design/prototype.html` is the starting point.
9. There is no separate vault mode. Ask covers everything from general questions to questions about my notes, and a context picker (vault, email, calendar and tasks) chooses what the agent may read in each chat, like choosing a repo in Claude (spec 14).
10. The app is named js ai. Sources are called connectors. The old review queue is replaced by the daily digest, which runs my `/daily full` command from the vault through the connectors and has its own screen (spec 15).
11. Tasks and schedule live in one calendar view, not on separate lists. There is no progress bar (decided by John).
16. The app opens on a dashboard that shows only today's goal (one line I write myself), my top three goals, and my top three deadlines. The top bar has only the menu button, and the slide out drawer lists dashboard, calendar, agent, money, digest, settings (decided by John).
17. I can add tasks and events in the app. They are saved only in the app (source `manual`) and never written to Google Calendar, Reminders, or the vault. The calendar merges them with everything else so there is still one place to look, but it does mean I may capture things in more than one place (decided by John).
15. Navigation: the slide out drawer is the main menu. Settings holds preferences, connectors, and agent activity, and connectors sit directly under settings, not under preferences (decided by John).
14. Money is a screen with a plain list of transactions and the bank for each, like Rocket Money's activity list without charts or totals. Read only, demo data first (spec 16) (decided by John).
13. The daily digest is its own screen again (it was briefly a message in the agent thread) and follows my `/daily full` command (spec 15). The app uses one font family with no serif and no italics (decided by John).
12. The agent is one page with a mode toggle: ask and homework, with room for more modes later. Each mode has a picker for its context: sources for ask, course for homework (decided by John).

## Global open questions
1. Which Google account holds the calendar, and is the Gmail digest in the same account?
2. Where will production run (Railway, Fly, Cloud Run, or Supabase functions)? Decide before spec 09.
