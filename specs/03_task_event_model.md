# 03 Shared task and event model

## Purpose
Every source converts its data into the same two shapes, tasks and events, so the priority engine and the API never care where something came from.

## Tables (SQLAlchemy models plus an Alembic migration)

### tasks
1. `id` integer primary key.
2. `user_id` integer, default 1.
3. `source` text: one of `obsidian`, `gmail_digest`, `reminders`, `manual`. `manual` items are created in the app and exist only in my database. A manual event is stored in `events` with source `manual`.
4. `source_ref` text: stable reference inside the source (for example a file path plus a fingerprint, or an email message id plus an item index).
5. `fingerprint` text: stable identity hash (see rules below). Unique together with `user_id` and `source`.
6. `title` text, required.
7. `due_at` timestamp in UTC, nullable.
8. `due_is_date_only` boolean. When true, the due moment is the end of that local day in `user_timezone`.
9. `effort_minutes` integer, nullable.
10. `importance` integer from 1 to 5, nullable (default 3 is applied by the engine, not stored).
11. `status` text: `open`, `done`, `gone`. `gone` means the source no longer contains it.
12. `snoozed_until` timestamp in UTC, nullable.
13. `needs_review` boolean, default false.
14. `review_reason` text, nullable.
15. `created_at`, `updated_at`, `last_seen_at` timestamps in UTC.

### events
1. `id`, `user_id`, `source` (`google_calendar` now, `outlook` later), `source_ref` (provider event id), `calendar_id`.
2. `title`, `start_at` and `end_at` in UTC, `all_day` boolean, `busy` boolean, `status` (`confirmed`, `tentative`, `cancelled`), `location` nullable.
3. `updated_at`, `last_seen_at`.
4. Unique together: `user_id`, `source`, `calendar_id`, `source_ref`, and the start time for recurring instances.

### sync_runs
`id`, `source`, `started_at`, `finished_at`, `status` (`ok`, `error`, `partial`), `items_seen`, `items_changed`, `error_summary` (short, no private text), `duration_ms`.

### oauth_tokens
`id`, `user_id`, `provider`, `encrypted_blob`, `updated_at`.

### llm_usage
`id`, `at`, `purpose` (`extraction` or `explanation`), `model`, `input_tokens`, `output_tokens`.

### explanation_cache
`key` (hash of inputs), `text`, `created_at`.

## Fingerprint rules
1. A fingerprint identifies "the same task" across syncs even when position moves.
2. Normalize the title: lowercase, trim, collapse whitespace, strip checkbox markers and metadata tokens.
3. Fingerprint is a SHA 256 of `source`, the source specific scope (file path for Obsidian, message id for email), the normalized title, and an occurrence counter for exact duplicates within the same scope.
4. If I edit a task's title, it becomes a new task and the old one becomes `gone`. This is accepted behavior for v1.

## Upsert semantics
1. A sync sees a set of items. For each, upsert by fingerprint and update fields and `last_seen_at`.
2. Items of that source and scope that were not seen become `gone`, but only when the sync finished successfully. A failed sync never marks anything `gone`.
3. A task marked done in the source becomes `done`. A `done` or `gone` task that reappears becomes `open` again.
4. Fields I set locally (`snoozed_until`, `importance` overrides) must survive a sync. Sources only overwrite the fields they own.

## Time rules
1. Store UTC everywhere.
2. Date only due values are converted to end of local day (23:59:59) in `user_timezone`, then to UTC, with `due_is_date_only` true.
3. All day events store start and end as local midnight boundaries converted to UTC, with `all_day` true.

## Pydantic schemas
`TaskIn`, `EventIn` (what sources produce), `TaskOut`, `EventOut` (what the API returns). Validation rejects empty titles and end before start.

## Acceptance criteria
* AC3.1 Migration creates all tables on SQLite.
* AC3.2 Upserting the same task twice produces one row.
* AC3.3 A task missing from a successful sync becomes `gone`. A task missing from a failed sync stays unchanged.
* AC3.4 A `gone` task that reappears becomes `open`.
* AC3.5 `snoozed_until` survives a sync that updates the same task's title text case.
* AC3.6 A date only due value converts to 23:59:59 local time, stored as the correct UTC instant, including across a daylight saving change.
* AC3.7 An all day event stores correct UTC boundaries for America/New_York.
* AC3.8 `EventIn` with end before start is rejected.
* AC3.9 Two identical titles in the same scope get different fingerprints through the occurrence counter.

## Out of scope
Any source specific parsing. Recurring tasks.

## Open questions
None.
