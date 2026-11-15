# 11 Outlook calendar (BLOCKED until IT approves)

## Gate (all must be true before any work starts)
1. I asked Cox IT or security whether a personal tool I run may read my work calendar, and I have a written yes (email or ticket).
2. The approval names the allowed access (read only calendar) and any conditions, such as where data may be stored.
3. I recorded the approval reference in `docs/CHECKIN_LOG.md`.

Until then: no Cox calendar data enters this project, its database, its logs, or its tests. Do not use real work data as fixtures.

## If approved, scope
1. Microsoft Graph, delegated, calendar read only permission, using the narrowest scope available.
2. A new source module `app/sources/outlook.py` that produces the same `EventIn` shape as Google Calendar, with source `outlook`.
3. Store only title, times, location, and busy state. No attendees, no bodies.
4. Honor any retention or hosting condition from IT.

## If approval is denied or conditional
Fallback options to discuss with me: manually copy only the busy blocks into a personal Google calendar, or skip work meetings and accept the limitation. Do not attempt workarounds that bypass policy.

## Acceptance criteria (only after the gate opens)
* AC11.1 Outlook events appear in `/today` alongside Google events with correct time zones.
* AC11.2 No event descriptions or attendee data are stored.
* AC11.3 Failure of the Outlook source does not affect other sources.
* AC11.4 The approval reference is recorded in the check in log.
