# 18. Goal follow through

Asked for by John on 2026-11-19. The ideas come from two places: research on what makes people follow through (implementation intentions, mental contrasting, the progress principle, the goal gradient, never missing twice, end of day reflection), and a video on reinventing yourself (process beliefs, the say/do ratio, inputs over outcomes, the "mailbox" approach to outcome goals, self talk right after something hard, stoic sparring).

## Why
A goal app fails when it makes you feel productive instead of making you act. Everything here pushes one of three things: what to do next and when, proof that you did it, and an honest look back.

## Requirements
1. **The #1 task with its time block.** `/today` gains `done_today` (tasks marked done in the app since local midnight). The app shows the #1 task heavier than #2 and #3, together with its suggested block, labelled as deep work, plus the if-then line from requirement 2.
2. **The obstacle and the if-then plan.** `daily_checkin(day, obstacle, if_then, top_task_title, did_top, why_not, let_go, updated_at)`. `GET /checkin/today` and `PUT /checkin/today` (partial: only the fields sent change). The app asks "what's most likely to stop you today?" and then "if that happens, I'll ...". Each field holds up to 200 characters.
3. **Inputs over outcomes.** `goals(id, name, kind input|outcome, unit, target, current, created_at, archived)` and `goal_logs(goal_id, day, count)`. An input goal has a daily target (for example "leetcode problems, 1 a day"). An outcome goal has a total and a current value (for example "Roth IRA, 7500, now 1450"). Endpoints: `GET /goals`, `POST /goals`, `PATCH /goals/{id}`, `DELETE /goals/{id}` (which archives it), and `PUT /goals/{id}/today {count}` (sets today's count).
4. **Never miss twice.** For each input goal `GET /goals` returns `today`, `last7` (oldest to newest, today last), `hit7` (days in last7 that met the target), `missed_twice` (yesterday and the day before both missed the target, and both are on or after the day the goal was created), and `total30`. The app shows "x of 7" and says "missed twice. today counts." in words, with no red. One missed day is never flagged.
5. **The nightly check-in and the say/do ratio.** At 9 pm a local notification asks "did #1 happen?". The app shows a check-in card from 9 pm until it is answered: did #1 happen (yes or no), why not (if no), and one thing outside your control to let go of. `GET /checkin/today` also returns `yesterday` (top_task_title, did_top, why_not) and `say_do` (kept and of, over the 14 days before today that have an answer). When yesterday's #1 slipped, the dashboard shows its why-not line with "never miss twice".
6. **Self talk after a win.** Marking a task done, or hitting an input goal's target, shows one short glass toast: "that's the type of person you are." under one of the identity lines from `/digest`, rotated. The toast is never shown for anything else.
7. **Outcome goals in the mailbox.** Outcome goals sit at the bottom of the dashboard under "in the mailbox", as quiet progress bars. Inputs are the loud part of the screen.
8. All of this lives in the agent's own database. Nothing is written to any outside service, and check-in text is never logged or sent to the LLM.

## Acceptance criteria
* AC18.1 `PUT /checkin/today` with only `obstacle` keeps the earlier `if_then`, and `GET` returns both.
* AC18.2 Check-in fields over 200 characters get a 422.
* AC18.3 `say_do` counts only days before today that have an answer: 3 kept of 4.
* AC18.4 `yesterday` returns yesterday's answer and why-not.
* AC18.5 Create an input goal, set today to 2 against a target of 1: today is 2, last7 ends in 2, and hit7 is 1.
* AC18.6 missed_twice is true after two missed days, false after one, and false for a goal created yesterday.
* AC18.7 An outcome goal returns current and target, and `PATCH` updates current.
* AC18.8 `DELETE` archives a goal, so it is no longer listed, and its logs stay.
* AC18.9 Bad goal input gets a 422: kind not input or outcome, target below 1, a name over 60 characters, or a negative count.
* AC18.10 `/today` `done_today` counts tasks marked done in the app since local midnight only.
* AC18.11 Every new endpoint needs the bearer token.

## Not in this spec
A home screen widget. Sharing data between the app and a widget needs an App Group, which a free Apple ID may not allow. The other way is storing the agent token in the widget's settings, which breaks the spec 10 rule that the token lives in the Keychain only. That is John's decision.
