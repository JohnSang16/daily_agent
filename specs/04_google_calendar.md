# 04 Google Calendar sync

## Purpose
Read my Google Calendar events into the shared `events` table. First real milestone: `/today` shows my actual schedule.

## Scope
1. A one time local script `scripts/google_auth.py` that runs the Google OAuth "installed app" flow, requesting the narrowest read only scopes, and saves the token.
2. `app/sources/google_calendar.py` with a `GoogleCalendarClient` interface and a real implementation, plus `sync_google_calendar()`.
3. A tiny `GET /today` stub (full version is spec 08) that returns the day's events so the milestone is visible.

## Auth and scopes
1. Scope for this spec: calendar read only. Gmail read only is added in spec 06 and requested in the same consent flow if convenient.
2. Dev: token file at `GOOGLE_TOKEN_PATH`, which is gitignored.
3. Production: token stored encrypted in `oauth_tokens` using `TOKEN_ENCRYPTION_KEY` (Fernet).
4. The code refreshes access tokens automatically and persists refreshed tokens.
5. **Known gotcha:** if the OAuth app stays in Testing publishing status, Google may expire refresh tokens after about 7 days. Options: (a) move the consent screen to production status for personal use, accepting the unverified app warning, or (b) re run the auth script weekly. Decide in the plan after verifying current Google documentation, and write the decision in this spec.

## Behavior
1. Sync window: from the start of yesterday to 14 days ahead in `user_timezone`. Both numbers are settings.
2. Calendars: those in `CALENDAR_IDS`, default `primary`.
3. Ask the API to expand recurring events into single instances, ordered by start time. Follow pagination until done.
4. Normalize each event into `EventIn`: title (fall back to "Busy" if missing), UTC start and end, `all_day` when the API gives a date instead of a date time, `location`, and `busy`.
5. `busy` is false for events marked as free (transparent). Events I declined are excluded. Cancelled events are stored with status `cancelled` and ignored by consumers.
6. Event descriptions are never stored in v1. Only title, times, location, and ids.
7. Idempotent: running twice yields the same rows.
8. Events in the window that no longer exist in the API are removed (or marked cancelled) after a successful sync only.
9. On any API failure, keep the old data, record a `sync_runs` row with status `error`, and use exponential backoff for rate limit responses with a small retry cap.

## Acceptance criteria
* AC4.1 With a fake client returning three events, sync stores three events with correct UTC times for America/New_York.
* AC4.2 An all day event is stored with `all_day` true and correct day boundaries.
* AC4.3 A recurring event returned as multiple instances yields distinct rows per instance.
* AC4.4 A declined event is excluded. A transparent event has `busy` false.
* AC4.5 Running sync twice produces no duplicate rows.
* AC4.6 An event deleted upstream is removed or cancelled after the next successful sync.
* AC4.7 A client that raises an error leaves existing events untouched and records an `error` sync run.
* AC4.8 A rate limit response triggers retries with backoff up to the cap, then fails cleanly (test with a fake sleeper).
* AC4.9 Pagination across two pages returns all events.
* AC4.10 Descriptions and attendee emails are not stored (assert absent from the model).
* AC4.11 `GET /today` stub returns today's events in my time zone and requires the bearer token.

## Manual verification (John)
Run the auth script, run the sync, and confirm that tomorrow's real events appear in `/today`. This is the Week 1 milestone.

## Out of scope
Writing events, incremental sync tokens, attendee details, Outlook.

## Open questions
1. Which calendars besides `primary` should be included?
2. Testing status versus production status for the OAuth consent screen (see gotcha above).
