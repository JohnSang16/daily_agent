# 19. Agent screen: ask and homework (study helper)

Asked for by John on 2026-11-20, with the study helper picked over the full browser agent. Spec 13 (the browser agent) stays gated, and nothing here drives a browser or submits anything.

## Requirements
1. The Agent screen has a mode switch (ask, homework), a message bar with a send button and dictation, suggestion chips, and a context chip, laid out as in design/DESIGN_NOTES.md item 5.
2. **Ask** uses `POST /ask`. The context chip sends `all` (vault, calendar), `notes` (vault only) or `tasks` (calendar only). Email stays off until spec 06 exists.
3. `POST /ask` also answers "daily full", "daily brief", "digest" and "brief" with the digest deadlines (up to seven, in order, with the overflow line), straight from the database with no LLM call (route `digest`).
4. **Homework** shows a course chip filled from `GET /courses`, which groups open iCollege tasks by course (the text in the last parentheses of the title, not counting "(closes)"). It also shows that course's upcoming assignments, soonest first. Tapping one fills the bar with "what does <assignment> cover?".
5. In homework mode `POST /ask` takes `course`. Search is limited to notes matching `SCHOOL_NOTES_GLOBS` (default `career/school/*`), and the course name is added to the search words. Every other ask rule applies: sources are shown, notes are untrusted data, there are no tools, the budget is enforced, and no logs are written.
6. A request to do the homework typed into the ask box ("work on hw 6") never starts anything by itself. The homework agent (spec 13) starts only from the "work on it" button on an assignment.
7. Dictation runs on the device (the Speech framework, with on device recognition required) and fills the bar. Nothing is sent until you tap send.

## Acceptance criteria
* AC19.1 "daily full" returns the digest deadlines in order with route `digest` and no LLM call.
* AC19.2 `GET /courses` groups open iCollege tasks by course, soonest first, and leaves out done tasks and other sources.
* AC19.3 With `course` set, only school notes are searched. A matching personal note is never a source.
* AC19.4 With `course` set, the course name is part of the search, so a note that names the course outranks one that doesn't.
* AC19.5 A homework request still returns route `homework`, mentions the tap, and starts nothing.
* AC19.6 `GET /courses` needs the bearer token.
