# 10 iOS app (phase 2, needs a Mac)

## Gate
Start only after specs 02 through 09 are done and `/today` is deployed and trustworthy for at least a week of real use.

## Purpose
A SwiftUI app that shows `/today`, lets me snooze or mark tasks, and uploads Apple Reminders to the backend (Reminders have no cloud API, so the phone must read and send them).

## Tools
Xcode (free), a Mac, and an iPhone. A free Apple ID signs the app for 7 days at a time, so reinstall from Xcode weekly. The paid developer program ($99 a year) removes the expiry and enables TestFlight. Decide when this phase starts.

## Design reference
The interactive prototype is `design/prototype.html` (published copy linked in `design/DESIGN_NOTES.md`). It sets the layout, colors, type, and motion. The app follows it unless I change it.

## Look and feel
Pure black and white, dark only, with no accent colors (status is shown with words, outlines, and fills instead of colors). One font family (Geist) everywhere, with no serif and no italics. Refined and understated, never loud: lots of space, light weights, all lowercase except titles, no cards, no divider lines, no bullet dots in plain lists (settings, connectors, steps, sources), and no subtitles under titles. The only dots are in the agenda and deadline lists, where a filled dot marks a task and a ring marks an event. The date title is large and light (about 46 px, weight 300, tight tracking) with the month and day under it in small muted type. Spacing and grouping separate things. Nothing animates unless I tap or swipe, except the small working dot.

## Navigation
1. **The slide out drawer is the main navigation.** It opens from the menu button or an edge swipe. Its header is the app name, "js ai". The items, in this order: dashboard, calendar, agent, money, digest, settings. The current screen is highlighted. The app always opens on the dashboard.
2. **Top bar:** only the menu button on the left. No screen name and no tabs. The menu button shows a small dot when there is an unread digest or an approval waiting, and the agent and digest items show the same dot inside the drawer.
3. **Digest** is its own screen, listed in the drawer between money and settings. The goals link on the dashboard also opens it. Opening it clears the unread dot. The agent page does not contain the digest.
4. **Settings** opens a settings screen with three items: preferences, connectors, and agent activity. Preferences holds the daily full time, the deadline cap, and agent approvals. Connectors (including bank accounts) sit directly under settings. Back moves up one level.
5. **Bottom sheets** for task, event, transaction, and connector details and for approvals.
6. **Message bar** fixed at the bottom of the agent page only: a text field, a microphone (disabled until voice exists), and send.

## Screens
1. **Dashboard (the default):** one quiet scroll with only what matters most. The weekday as a large light title with the month and day under it. Then "today's goal": one line I write myself (a text field with a save button, shown as large text with a small edit link once saved). Then "goals": my top three goals as a numbered list, each with one short line under it, with a small "digest" link (the goals come from the vision and why sections of `/daily full`). Then "deadlines": my top three deadlines as a numbered list, each with the day and time under it, with a small "calendar" link. Nothing else: no alert rows, no transactions, no totals, no cards, no progress bars. Pending approvals and an unread digest show only as the dot on the menu button and in the menu.
2. **Calendar:** one scroll. The selected weekday as a large light title with the month and day small under it (no other subtitle), a week strip that starts today and runs seven days, with dots on days that have items, a month toggle that expands a month grid, and then one agenda for the selected day, grouped under small morning, afternoon, and evening labels, with no divider lines. Each item has two lines: the title on top and the time under it. A filled dot marks a task and a ring marks an event, so the type is clear at a glance. Spacing between items does the separating. It mixes events, tasks ("due" time, with an outlined "first" tag on the top priority), and a "now" bullet on today. The app does not show free time anywhere. Tasks with no date appear under "anytime" on today. There is no separate task list and no progress bar. An "add" link sits next to the month toggle. It opens a sheet to add a task or an event: a name, a day (the next seven days), and a time (optional for tasks, defaulting to end of day; required for events, defaulting to 9:00am). Items I add are saved only in the app. Tapping one of them shows "added in the app" and a delete button.
3. **Agent:** one page with a mode switch at the top (ask and homework, with room for more). A context chip sits above the message bar, like choosing a repo in Claude. In ask it opens a sheet that turns the vault, email, and calendar and tasks on or off for that chat, and the chip shows the choice ("context: all", "context: vault, email"). Ask is a plain conversation with suggestion chips, and it handles everything from general questions to questions about my notes, showing source notes when it uses the vault. In homework the chip picks the course, and the page shows the active session: the live browser view, take over and full screen, a "ready to post or submit" row when approval is needed, a short step list, and other assignments with start buttons. A course with no active session shows an empty state with its assignments.
4. **Digest:** a large "Digest" title with the date and time under it, then the `/daily full` layout: mantra, vision, why, identity lines, a numbered deadline list (at most 7), an overflow line, a quiet note for any source that failed, and a short affirmation. Under it are two small actions, open everything for today and refresh. Built each morning and rebuilt on refresh. In the agent, asking for "daily full" opens this screen.
5. **Money:** a large light title, a bank filter chip, and a plain list of transactions grouped by day. Each transaction shows the merchant, then the bank and category, with the amount on the right (money in has a plus sign, no minus signs, no colors). Tap for a read only detail sheet. It shows demo data until a bank is connected (spec 16).
6. **Connectors:** reached directly from settings. A list of connected services with status and last read time. Tapping one shows what the agent may do (allowed tools) and what is blocked. A row to add a connector.
7. **Settings screens:** settings (preferences, agent activity), preferences (daily full time, deadline cap, agent approvals, connectors), connectors, and agent activity.
8. **Approval sheet:** says exactly what will be posted or submitted, reminds me to read it myself, and uses a two tap final approval.

## Live browser view
1. The Agent screen embeds the Kernel live view URL for the active session in a web view (WKWebView). The URL is a secret handed to the app by the backend per session.
2. Default is read only while the agent works. Take over switches to interactive and pauses the agent. Hand back resumes it.
3. Kernel documents that Safari needs a user tap before an embedded view receives keyboard input, so test typing inside the web view on a real iPhone early.

## Backend additions (written as their own small specs before coding)
0. `POST /items` and `DELETE /items/{id}`: create and delete tasks and events I add in the app, stored in my own database with source `manual`. They are never written to Google Calendar, Reminders, or the vault. They appear in the calendar, on the dashboard deadlines (when upcoming and not done), in `/today` ranking, and in the digest only if the digest spec says so.
0. `GET /goal/today` and `PUT /goal/today`: read and write the one line goal for the current day in my own database (`daily_goal` with date and text, 90 characters max). A local write only.
1. `POST /ingest/reminders`: accepts a list of reminders (id, title, due, completed). Creates and updates tasks with source `reminders`. Same upsert semantics as spec 03, including `gone` handling per upload.
2. `POST /tasks/{id}/snooze` and `POST /tasks/{id}/done`: local state changes. These are the only writes in the system and they touch only my own database, never an external source.
3. Auth upgrade path: replace the shared bearer token with Sign in with Apple, or keep the token stored in the iOS Keychain for personal use.

## Requirements
1. The token and backend URL are stored in the Keychain, never in source control.
2. The app reads Reminders through Apple's on device access after the user grants permission, and uploads only title, due date, and completion state.
3. The app never talks to Google, Gmail, or the vault directly. Only the backend does.
4. Offline: show the last fetched `/today` with a visible "last updated" time.
5. Minimum interactions: pull to refresh, tap a task, snooze.

## Acceptance criteria
* AC10.1 The app shows the real `/today` response on my phone.
* AC10.2 With the network off, the app shows cached data with an offline label.
* AC10.3 Granting Reminders permission uploads reminders and they appear in the ranking with source `reminders`.
* AC10.4 Snoozing a task from the app removes it from the ranking until the snooze time.
* AC10.5 The token is stored in the Keychain (inspect the code path) and does not appear in logs.
* AC10.6 Backend tests cover `/ingest/reminders`, snooze, and done endpoints, including 401 without a token.
* AC10.7 The Calendar and Agent switch, the drawer, the message bar, and the sheets match the prototype in behavior, and the app is dark only.
* AC10.8 An edge swipe opens the drawer and a swipe back or a tap on the scrim closes it.
* AC10.9 The Agent side shows a dot while an approval is pending and clears it after I decide.
* AC10.12 In ask mode with the vault context on, a question about my notes calls `POST /ask` and shows the answer with its source notes inline. With the vault context off, the app says so and does not search notes.
* AC10.18 Changing the context sheet changes what the backend is allowed to read for that chat, and the chip label updates.
* AC10.19 In homework mode, the course picker changes the shown session or empty state.
* AC10.13 The calendar view shows events and tasks (and a now marker) in one agenda for the selected day, with no separate task list, no progress bar, and no free time labels.
* AC10.20 Each agenda item shows its title on one line and its time on the line below, tasks use a filled dot and events a ring, and items are grouped under morning, afternoon, and evening.
* AC10.21 On a screen wider than a phone, the app is shown at phone size (390 px wide) as a framed, centered column and never stretches like a tablet layout.
* AC10.14 The week strip and month grid select a day, and days with items show a dot.
* AC10.15 The mode switch on the Agent page changes the page, the message bar placeholder, and the context chip, and a new mode can be added without redesigning the page.
* AC10.16 The Connectors screen lists each connector with status and shows its allowed and blocked actions.
* AC10.17 The digest screen shows the sections in the order of `/daily full`, with the identity lines and the deadline list numbered separately. The open everything action works for allowed links, falling back to one tap per item if the system blocks bulk opening.
* AC10.25 The drawer lists dashboard, calendar, agent, money, digest, and settings in that order, the app opens on the dashboard, and the current screen is highlighted. The top bar has only the menu button.
* AC10.28 The dashboard shows only the weekday title, today's goal (writable), the top three goals (numbered, with a short line each), and the top three deadlines (numbered, with day and time), and each list links to its full screen. It shows no transactions and no alert rows.
* AC10.31 Adding a task or event in the app shows it on the chosen day in the calendar and updates that day's dot. A task added with a near deadline can appear in the dashboard's top three deadlines. Deleting it removes it everywhere.
* AC10.32 Items added in the app are stored only in my database (source `manual`). No request is made to Google Calendar, Reminders, or the vault when adding or deleting them.
* AC10.30 Today's goal can be written, saved, edited, and cleared. It is stored per day in my own database (never sent to an outside service), survives closing the app, and starts empty on a new day.
* AC10.26 Settings leads to preferences, connectors, and agent activity, connectors is not nested under preferences, and back moves up exactly one level at a time.
* AC10.27 Choosing digest in the drawer opens the digest screen, highlights digest in the drawer, and clears the unread dot. Asking for "daily full" in the agent opens the same screen.
* AC10.24 The Money screen lists transactions grouped by day with the bank on each, a bank filter, and a read only detail sheet, and shows demo data until a bank is connected.
* AC10.22 If a source failed when the digest was built, the digest shows a quiet note naming it and does not claim to be complete.
* AC10.29 Plain lists (settings, preferences, connectors, activity, steps, sources) show no bullet dots. Only the calendar agenda uses dots, filled for tasks and a ring for events. Goals and deadlines on the dashboard use plain numbers.
* AC10.23 The app uses one font family with no serif and no italics anywhere.
* AC10.10 With a fake session, the live view loads in the web view and take over makes it interactive.
* AC10.11 All interactive elements have accessibility labels, and the layout works with large text sizes and reduced motion.

## Out of scope
Widgets, Apple Watch, push notifications (spec 12), App Store release.

## Open questions
0. Should yesterday's goal appear in tomorrow's digest (for example, as a done or not done line)?
1. Free signing versus the paid program.
2. Which Reminders lists to include.
3. SwiftUI with a web view for the live browser, or a cross platform tool. Default: SwiftUI.
