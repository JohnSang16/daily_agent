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

## Update 2026-11-19: money charts and goals
At John's request Money has an overview with a grouped bar chart (income in white, spend in gray), category bars, budget goal bars, holdings and a bank by bank view. These break the old "no charts, no progress indicators" line on purpose. They stay monochrome: bars are white on a dark track, and over budget is said in words, never in a color.

## Update 2026-11-23: money overview redesign
At John's request, borrowing Rocket Money's layout patterns while staying monochrome. The three figures and the grouped income/spend bar chart became one trend hero card: a big spend number, a day/month toggle, and a line and area chart (white line, white to clear gradient). Income moved from its own bars into a text only footer line. The category bars became a donut with a gray ramp, top 5 categories plus one "other" slice in the darkest gray. The budget goal bars became ring gauges in a horizontal scroll row, with a trailing add ring. Still no accent colors.

## Update 2026-11-23: banks and activity, income tab removed
Picked from localhost mocks. Banks opens with a glass net worth card (big number, one bar split into cash, savings and invested in white and two grays, what's owed below), then one glass card per bank. Activity opens with a spending calendar (this month as a monday first grid, each day shaded white by what was spent, tap a day to show only it), then a compact row of recurring bills, then filter chips (all, spending, income, pending, banks), a category symbol on each row and a net total per day. The income tab is gone: the activity income filter lists income, and the overview footer shows this month's income and net.

## Update 2026-11-24: trend chart and donut hand drawn, not Swift Charts
After repeated crashes traced to Swift Charts' own internals on the 7D range (confirmed via register dump, never resolved despite six targeted fixes), both the trend hero card's line and area and the category donut were replaced with plain GeometryReader/Canvas drawing. Same look, arithmetic computed and verified directly instead of handed to a closed source framework.

## Update 2026-11-25: money goals and the stretch card
At John's request Money has a fifth view, goals: the stretch goal (big number, a bar with a tick at the floor, days left), the budget as three columns showing what is left over the cap ("$120 / $205"), and savings and investing goals behind a season switch (2026, spring, summer), one two line row per goal. The dashboard shows the stretch goal as a card right under the date; tapping it opens money goals. This breaks the "no progress bars on the dashboard" line on purpose, for that one card only.
