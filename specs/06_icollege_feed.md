# 06 iCollege calendar feed to tasks

## Purpose
Turn my college course due dates into shared `tasks`. iCollege (D2L) publishes a private calendar feed (`.ics`) with exact due dates, so no email parsing and no LLM is involved. Replaces the Gmail digest plan (`06_gmail_digest.md`).

## Access
1. The feed URL contains a private token. It lives only in a local file (`ICOLLEGE_FEED_URL_PATH`, default `~/.config/icollege-feed-url`), never in the repo, env vars, logs, or audit rows.
2. One allowlisted outbound rule: `GET` on `gastate.view.usg.edu` path `/d2l/le/calendar/feed/.*`. Read only.
3. The feed content is untrusted data. It is parsed as text only.

## Behavior
1. Fetch the feed, unfold continuation lines, split into events.
2. Keep an event only if its summary ends in `- Due` or `- Availability Ends` and its start moment is in the future or passed within the last 14 days (so a missed one shows as overdue instead of vanishing). Everything else (lectures, announcements, older items) is ignored.
3. Each kept event becomes a task: source `icollege`, scope `feed`, title is the summary without the suffix (`(closes)` appended for Availability Ends) plus the course location when present, due at the event's exact start moment (UTC).
4. Idempotent. A task whose event disappears from the feed (past, removed, or changed title) becomes `gone` after a successful fetch only.
5. On any failure keep the old tasks and record an `error` sync run with the exception class only. Never put the URL in a log, a run summary, or an audit row.
6. Logs carry counts only, never titles.
7. Stale after 6 hours without a success.

## Acceptance criteria
* AC6.1 A fixture feed with three future due events yields three tasks with the right UTC due moments.
* AC6.2 Lecture events, past events, and non due summaries are ignored.
* AC6.3 `Availability Ends` events become tasks marked `(closes)`.
* AC6.4 Folded (wrapped) feed lines are unfolded correctly.
* AC6.5 Running sync twice produces no duplicate tasks.
* AC6.6 An event removed from the feed marks its task `gone`.
* AC6.7 A fetch failure leaves existing tasks unchanged and records an `error` run with no URL text.
* AC6.8 The feed rule is in the outbound allowlist, and a different path on the same host is denied.
* AC6.9 Logs contain no task titles and no URL.

## Out of scope
Submission status, grades, announcements, writing to Reminders (the existing script does that), multiple feeds.
