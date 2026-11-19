# Design notes

Interactive prototype: https://claude.ai/artifact/JRUgUFE6HJZ8eKprNDSCwj
Local copy: `design/prototype.html` (open on a phone, or narrow the desktop window).

## Direction
Pure black and white. Dark only, no tinted blues, no accent colors, no yellow or red status colors. Sleek, simple, understated, professional, and a little nonchalant. It should feel like a personal Jarvis: quiet until needed. Less is more.

## Structure
1. App name: js ai (shown at the top of the drawer).
2. The slide out drawer is the main navigation: dashboard, calendar, agent, money, digest, settings, in that order. The app opens on the dashboard. The top bar has only the menu button.
3. The dashboard is the default and shows only what matters most: the large light weekday title, then "today's goal" (one line I write in, large text once saved), my top three goals (numbered, one short line each), and my top three deadlines (numbered, day and time under each). Small links go to the digest and the calendar. No alert rows, no transactions, no totals, no cards, no charts, no progress bars. Pending items show only as a dot on the menu button.
4. Calendar is one view, with a small "add" link beside the month toggle that opens a sheet to add a task or an event (saved only in the app): a large light weekday title with the month and day under it, a week strip that starts today, an expandable month grid, and one agenda for the selected day. No subtitle, no progress bar, no separate task list, and free time is never shown.
5. Agent is one page with a mode switch (ask and homework) and a message bar at the bottom. Above it sits a context chip, like choosing a repo in Claude: in ask it picks what the agent can read (vault, email, calendar and tasks), and in homework it picks the course.
6. The daily digest is its own screen, laid out like the `/daily full` command: a large "Digest" title with the date and time under it, then mantra, vision, why, identity, numbered deadlines, an overflow line, a quiet note if a source failed, and the affirmation. The drawer lists it, and the dashboard alert row opens it.
7. Money is a plain list of transactions grouped by day, with the bank on each (merchant, then bank and category, amount on the right, a plus sign for money in, no minus signs). A bank chip filters the list.
8. Settings holds three things: preferences, connectors (including banks), and agent activity. Preferences holds the daily full time, the deadline cap, and agent approvals.
9. On screens wider than a phone the prototype shows a 390 px framed column so it never looks like a tablet layout. No cards, no dashboards, no progress indicators.

## The one memorable element
The large, light weekday title. "Friday" in big thin type with the date quietly under it, then one agenda grouped by morning, afternoon, and evening.

## Tokens
Colors (neutral grays only): background #000000, surface #0B0B0B, raised #161616, line #242424, titles #FFFFFF, body #DCDCDC, secondary #A4A4A4, tertiary #858585 (the lowest allowed for text). No other hues anywhere.
Lists have no bullet dots. Settings, connectors, steps, and sources are plain rows separated by spacing. The only dots are in the calendar agenda, where a filled dot means a task and a ring means an event.
Meaning without color: white fill means a task or the primary action, a ring means an event, an outline means secondary or needs attention, a small outlined "now" tag marks the current time, and every status also uses words.
Type: one family only, Geist. No serif and no italics anywhere. Weekday title 46 px at weight 300 with tight tracking. Other titles 26 to 28 px at weight 400. Body 14.5 px. List titles 16 px. Secondary text 12 to 13.5 px. Heaviest weight is 500.
Case: everything is lowercase except titles and proper names. The digest screen keeps the capitalization of its source text, with lowercase section labels.
Shape: pill buttons and a pill message bar, 24 px sheet corners, 1.4 px icon strokes.
Motion: 380 ms ease out for the switch, drawer, and sheets. The only ambient motion is the small pulsing working dot. Reduced motion is respected.

## Voice and copy
Short, calm lowercase lines (for example "morning. the ethics post is due in 55 minutes."): "afternoon. this one first.", "you've got room.", "gmail digest is 31 hours old". Only titles use sentence case. Buttons are lowercase and say what happens: "work on it", "approve and submit", "take over". Warnings say what is wrong in one line.

## Accessibility
Visible focus, labels on icon buttons, 44 px touch targets, status shown with words and not color alone, safe areas respected, reduced motion respected.

## Not yet designed
Money, voice, notification styles, onboarding, empty states for a new account.

## Update 2026-11-19: glass and springs
At John's request the iPhone app uses frosted glass surfaces, a soft sheen on the primary button and spring motion. Still no accent colors, and Reduce Motion is respected. The 380 ms ease out above is still used for plain fades.
