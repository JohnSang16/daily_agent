# 07 Priority engine

## Purpose
A pure, deterministic function that ranks tasks by nearest deadline and checks whether the work fits in my free time.

## Interface
```
rank(tasks, events, now, config) -> RankingResult
```
No database, no network, no clock calls inside. Everything arrives as arguments.

Config: `user_timezone`, `work_start`, `work_end` (daily availability window, applied every day unless overridden), `default_effort_minutes`, `horizon_days` (default 14), `min_block_minutes` (default 15).

## Eligibility
1. Only tasks with status `open`.
2. Exclude tasks where `snoozed_until` is after `now`.
3. Tasks with `needs_review` stay in the list and carry a flag.

## Ordering (nearest deadline first)
1. Compute the due moment: `due_at` in UTC. Date only values already mean end of the local day (spec 03).
2. Dated tasks sort by due moment ascending. Overdue tasks therefore come first, with the oldest due first.
3. Tie breakers for equal due moments: importance descending (default 3 when missing), then effort ascending (default effort when missing), then `created_at` ascending, then `id` ascending.
4. Undated tasks come after all dated tasks, sorted by importance descending, then `created_at` ascending, then `id`.

## Feasibility check
1. Build my available time between `now` and each due moment: working hours windows within the horizon, minus busy events (merge overlaps; ignore events that are not busy or are cancelled), dropping leftover blocks shorter than `min_block_minutes`.
2. Walk the ranked dated tasks in order, keeping a running total of effort (using the default effort when missing).
3. A task is `at_risk` when the running effort total through that task is greater than the available minutes before its due moment. Overdue tasks are always `at_risk`.
4. Record `free_minutes_before_due` and `cumulative_effort_minutes` for each dated task.

## Reason codes (per task, in a list)
`OVERDUE`, `DUE_TODAY`, `DUE_TOMORROW`, `DUE_THIS_WEEK`, `NO_DUE_DATE`, `AT_RISK`, `TIE_BROKEN_BY_IMPORTANCE`, `TIE_BROKEN_BY_EFFORT`, `NEEDS_REVIEW`, `DEFAULT_EFFORT_USED`.

## Result shape
1. `ranked`: list of items with `task_id`, `rank` (starting at 1), `reasons`, `at_risk`, `free_minutes_before_due`, `cumulative_effort_minutes`.
2. `top_task_id`: the first ranked item, or null.
3. `free_blocks_today`: the free blocks remaining today in local time after `now`.
4. `suggested_block`: the earliest free block today that is at least the top task's effort long, or null.

## Worked examples (these become tests)
1. Two tasks due tomorrow and next week: tomorrow's ranks first.
2. A task due yesterday and one due tomorrow: the overdue one ranks first and has `OVERDUE` and `AT_RISK`.
3. Equal due moments, importance 5 versus 3: the 5 ranks first with `TIE_BROKEN_BY_IMPORTANCE`.
4. Equal due and importance, effort 30 versus 90: the 30 ranks first with `TIE_BROKEN_BY_EFFORT`.
5. A task needing 8 hours due in 3 hours: `AT_RISK` with free minutes less than 480.
6. A busy all day event removes that day's working window from available time.
7. A snoozed task is excluded until its snooze time passes.
8. An undated task ranks after every dated task.
9. Daylight saving change inside the horizon does not shift working hours.

## Acceptance criteria
* AC7.1 to AC7.9 correspond to worked examples 1 through 9.
* AC7.10 The function is pure: calling it twice with the same inputs returns equal results, and it does not read the system clock (test by passing `now` and asserting behavior at two different values).
* AC7.11 Input lists are not mutated.
* AC7.12 `suggested_block` is null when no free block is long enough.
* AC7.13 A property style test with randomized tasks always returns a result sorted consistently with the ordering rules.
* AC7.14 Performance: 500 tasks and 500 events rank in under one second.

## Out of scope
Learning from my behavior, dependencies between tasks, splitting work across days.

## Open questions
1. Are my working hours the same every day? Do I want per weekday windows (for example classes or shifts)?
2. Should events marked tentative block time? Default: yes.
