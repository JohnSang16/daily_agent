# Triage, 2026-11-19

The iOS pass on branch `ios_ux_pass` fixed the frontend bugs below. The backend bugs are listed for triage only and have not been fixed. Each one was found by reading the code, and the ones marked "proved" were reproduced with a throwaway script against in memory data. None of them is caught by the current 223 tests.

## Frontend fixes shipped (ios_ux_pass)
- Haptics never fired on pill buttons or "mark done", because the trigger was the label or id, which never changes. Each tap now drives the trigger.
- The calendar day strip fired its selection haptic seven times per tap (it was attached to every day). It now fires once.
- Bank switches snapped back to their old position until five reloads finished. They now flip at once, and flip back only if the agent refuses.
- The add item sheet could be saved twice by a double tap, which made duplicate items, and it waited for 8 reloads before closing. It now has a saving state, is disabled while the title is empty, and closes as soon as the agent has the item.
- Snooze, done and budget changes made you wait on the network before the sheet closed. The sheet now closes at once, the row animates out, and the agent catches up behind it.
- Offline on Digest, Money or Calendar showed "loading." forever. These screens now say "offline. can't reach the agent.", or show the real problem.
- One failed call left its problem line on every screen until the dashboard refreshed. Any successful call now clears it.
- The calendar showed "nothing on this day." while the week was still loading. It now shows a loading line, and fetches the six later days side by side instead of one after another.
- The money screen made six calls in a row and fetched banks twice. It now makes five calls side by side.
- White switch tracks hid the white iOS knob. Switches now use a light gray track.
- The empty goal could be saved, and there was no way to cancel an edit. Save is now disabled when the goal is empty, the keyboard's done key saves, and editing has a cancel.
- An address typed without `http://` silently failed. Addresses are now cleaned up when saved.
- The dashboard only loaded once per launch. It now refreshes when it is more than 5 minutes old, on screen switches and when the app comes back to the front.
- Bank names were forced to lowercase. They keep their own case now, because they are proper names, and sheet titles use sentence case.

Look: the drawer follows your finger and settles with a flick, and the page rounds its corners and leans back while it opens. A faint light sits behind the glass, the page fades out under the menu button as you scroll, numbers use tabular digits, and every sheet uses the same frosted style.

## Backend bugs, ranked
P0 means data loss, wrong money, or a crash on a normal path. P1 is a wrong result on a plausible path, and P2 is an edge case or a robustness gap.

| # | Pri | Where | Bug | Fix | Proved |
|---|-----|-------|-----|-----|--------|
| 1 | P0 | `app/sources/google_calendar.py:173` | An event that started before the sync window (a multi day all day event) is not found among the existing rows, so it gets inserted again, the unique key fails, and every calendar sync crashes until the event ends | Look up existing rows by `end_at > tmin`, not by start | yes |
| 2 | P1 | `app/sources/obsidian.py:35` | `- [ ] essay 📅` with no date crashes the whole vault sync (`d` is None) | If there is no match, mark it "unreadable due date" | yes |
| 3 | P1 | `app/banks.py:98` | One bank with an expired login stops the loop, so no bank after it syncs | Catch errors per bank, record the failure and continue | read |
| 4 | P1 | `app/banks.py:45`, `app/api/banks.py` | Connecting a bank that is already connected doubles its balances and transactions | Refuse or replace a bank that is already connected, then add Plaid's re-authorization flow | read |
| 5 | P1 | `app/money.py:13` | All of `TRANSFER_OUT` is dropped, so ATM cash and Zelle or Venmo rent disappear from spend and from the TOTAL budget | Drop only transfers between your own accounts and card payments. This needs a spec 16 wording change | yes |
| 6 | P1 | `app/sources/icollege.py:41` | Past items are skipped, so a missed assignment vanishes the moment it is due instead of showing as overdue | Keep past items for `stale_overdue_days`. This needs a spec 06 change | read |
| 7 | P1 | `app/tasks_sync.py:100` | "Done in the app" never resets, so a task deleted and then re-added with the same title stays hidden forever | Clear the flag when a task is marked gone (spec 10a) | yes |
| 8 | P1 | `app/llm/explain.py` | Several `/today` calls on a cold cache all miss, each calls the LLM, and the second cache insert hits a duplicate key | Use an insert that ignores conflicts, or precompute the explanation after each sync (build next 4). The app now warms the cache with one call first | read |
| 9 | P2 | `app/sources/google_calendar.py:75` | Calendar ids with `#` (holiday calendars) build the wrong path and get a 404 | `quote(calendar_id, safe="")` | yes |
| 10 | P2 | `app/api/today.py:118` | The privacy check for `/today` is hard coded to `cox/` and ignores `ASK_LLM_BLOCKED_GLOBS` | Share one glob setting | read |
| 11 | P2 | `app/api/today.py:157` | `?date=` still returns the same top 50 ranking, so with more than 50 open tasks, later week tasks never show in the strip | Add a week endpoint (build next 3) | read |
| 12 | P2 | `app/api/local.py:38` | Manual items have no limits: a negative effort hides at risk tasks, 0 becomes 60, and titles can be any length | `Field(ge=1, le=1440)` and `max_length=300` | read |
| 13 | P2 | `app/api/today.py:27` | Warnings read the full `sync_runs` history on every request, and a source that has been removed stays "out of date" forever | Read only the latest run per configured source | read |
| 14 | P2 | `app/api/banks.py:123` | Deleting a bank needs `TOKEN_ENCRYPTION_KEY` first, so without the key you cannot remove the local data (AC16.8) | Delete locally always, and disconnect remotely only when the key is set | read |

Also noted, and allowed by the spec: reminders are matched by title, so two reminders with the same title can swap their done and snooze state.

## What to build next, in order
1. Fix backend bugs 1 to 3 (calendar crash, vault crash, bank loop). These are small diffs, and each one stops a whole source from going dark.
2. Run the app on the phone from Xcode once. It has only been compile checked and logic checked, so run every screen against `docs/TRIAGE.md` and the README.
3. Week endpoint `GET /week?start=&days=7`: one ranking, one explanation, no 50 item cutoff. It replaces the app's 7 calls and closes bugs 8 and 11.
4. Agent (ask) screen in the app. `POST /ask` already exists, so this is a frontend only build: a pill message bar and a context chip, per the design notes.
5. Bank health: errors per bank (bug 3), the re-authorization flow (bug 4), and the Plaid webhook from spec 16.
6. The money transfer rules (bug 5): decide the spec 16 wording, then fix. It is wrong money, but fixing it needs your call.
7. Gmail digest source (spec 06). The sync runner already expects `gmail_digest`.
8. Precompute the explanation after each sync, so `/today` only reads the cache.
9. Encrypt the Google token at rest, using the existing `oauth_tokens` table and the existing encryption helper.
10. Calendar month grid, then the Geist font, then approvals.
11. Pruning for `sync_runs`, `outbound_calls` and `llm_usage`, then hosting (spec 09) when the Mac should be able to sleep.
