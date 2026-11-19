# 10a Backend additions for the iOS app (local writes only)

Splits out the "Backend additions" list from spec 10 so it can be built and tested before any phone work. Every endpoint needs the bearer token. Every write touches only my own database, never Google, Reminders, or the vault (spec 17).

## Endpoints
1. `POST /items` creates a task or an event with source `manual`. Body: `kind` (`task` or `event`), `title`, and for a task an optional `due` (ISO date or date time), `effort_minutes`, `importance`; for an event `start`, `end`, optional `all_day`. Returns `{"id": "task-12"}` or `{"id": "event-5"}`.
2. `DELETE /items/{id}` deletes a manual item by that id. Anything not created through `POST /items` is refused with 404.
3. `GET /goal/today` returns `{date, text}` (`text` null if none) for the current day in my time zone. `PUT /goal/today` with `{text}` saves it, 90 characters max (422 beyond that). A new day starts empty.
4. `POST /ingest/reminders` takes `{reminders: [{id, title, due, completed}]}` where `due` is an ISO date, an ISO date time with offset, or null. It upserts tasks with source `reminders` using the spec 03 rules. A reminder missing from a later upload becomes `gone`. `completed` becomes `done`.
5. `POST /tasks/{id}/snooze` with `{until}` (timezone aware, in the future) hides the task from the ranking until then. `POST /tasks/{id}/done` marks it done. A task marked done here stays done through later source syncs (a `locally_done` flag), until I delete it from the source.

## Data
New table `daily_goal(day, text, updated_at)` and a `tasks.locally_done` column, with an Alembic migration.

## Acceptance criteria
* AC10a.1 A manual task appears in `/today` ranking, a manual event in the day's events, and deleting either removes it.
* AC10a.2 `DELETE /items/{id}` on a task from any other source returns 404 and changes nothing.
* AC10a.3 `PUT /goal/today` saves a goal, `GET` returns it, 91 characters is rejected, and the next day reads empty.
* AC10a.4 Uploading three reminders creates three `reminders` tasks (date only due and exact due both parse), `completed` yields `done`, and omitting one in the next upload marks it `gone`.
* AC10a.5 A snoozed task is absent from the ranking until the snooze time and present after it. A past `until` is rejected.
* AC10a.6 A task marked done leaves the ranking and stays done after a source sync that still lists it as open.
* AC10a.7 All endpoints return 401 without the token.
* AC10a.8 The Alembic migration creates `daily_goal` and `tasks.locally_done`.

## Out of scope
Editing items, recurring items, the app itself.
