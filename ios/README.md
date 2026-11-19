# js ai (iPhone app)

A SwiftUI screen for the daily agent. It only talks to the agent's API, never to Google, Gmail or the vault directly (spec 10, requirement 3). The address and token are kept in the iOS Keychain.

## What is built (v0.1)
- Dashboard: weekday title, the agent's one paragraph explanation, today's goal (saved to the agent), top three deadlines, today's schedule, warnings in plain words, "updated" or "offline" line. Pull to refresh. Tap a deadline to snooze it or mark it done.
- Calendar: big weekday title, a seven day strip starting today (dot on busy days), the day's agenda split into all day, morning, afternoon and evening (filled dot is a task, ring is an event, "first" tag on the top priority), and an "add" sheet that saves a task or event in the agent only (never to Google Calendar). Month grid not built yet.
- Digest: the daily brief from `GET /digest`: the mantra, one vision line and the newest WHY from your reflections (all read from the vault), then up to seven hard deadlines in order with an overflow line, and quiet notes about stale or failed sources.
- Money: four views. Overview (this month's spent, income and net, a spend vs income bar chart for six months, where it went by category, and budget goals you set with a limit and see as bars), Banks (where your money sits: cash, savings, invested, owed on cards and loans, net, then every bank with its accounts, balances and an on/off switch each), Income (the full income log by month with subtotals) and Activity (the plain transaction list).
- Settings: agent address and token, "save and test", upload open Reminders (title, due, done only, never writes back).
- Offline: shows the last good response with "offline. last updated ...".
- Slide out drawer (menu button or edge swipe), pure black and white, dark only.

## Look and motion (added 2026-11-19 at John's request)
Glass and springs, still monochrome so the design stays black and white. Real Liquid Glass (`glassEffect`) on iOS 26 and later, frosted material with a hairline highlight before that. Spring animations on the drawer (the screen leans back, rounds its corners and slides over), screen switches, the calendar day picker (one white disc glides between days), and sheets. Sections fade and rise in one after another. Buttons shrink slightly when pressed. Light haptics on the drawer, day picks and mark done. Reduce Motion in iOS settings turns the movement down to simple fades.

## Not built yet
Agent (ask) screen, the calendar month grid, the Geist font (uses the system font), approvals, Sign in with Apple. It has never been run on a device or simulator, only compile checked and logic checked from the command line (see below), so expect small fixes on the first run.

## Run it (on the Mac that has Xcode)
1. `git pull` this repo, then open `ios/DailyAgent/DailyAgent.xcodeproj`.
2. Xcode, Settings, Accounts: add your Apple ID.
3. Click the DailyAgent target, Signing and Capabilities, set Team to your Personal Team. If it says the bundle identifier is not available, change `com.johnsang.dailyagent` to anything unique.
4. Plug in the iPhone, tap Trust. On the phone turn on Settings, Privacy and Security, Developer Mode (it restarts). Pick the phone at the top of Xcode and press Run.
5. First launch on the phone: Settings, General, VPN and Device Management, trust your Apple ID.
6. In the app, Settings: address `http://<the agent Mac's Tailscale 100.x address>:8000` and the token from `daily_agent/.env`, then "save and test". The agent must be started on that address (`--host <100.x address>`), see `personal/personal-projects/daily-agent-tailscale-setup.md` in the vault. The phone and the agent Mac both need Tailscale on.
7. A free Apple ID signs the app for 7 days. Press Run again from Xcode to refresh it.

## App icon
The icon lives at `ios/DailyAgent/Sources/Assets.xcassets/AppIcon.appiconset/AppIcon.png` (1024 by 1024, no transparency). The current one is a placeholder. To change it, replace that file with your own 1024 square PNG with the same name, or in Xcode open Assets, then AppIcon, and drag a new image into the slot. iOS rounds the corners itself, so do not round them yourself.

## Regenerating the Xcode project
`project.yml` is the source. `brew install xcodegen`, then `cd ios/DailyAgent && xcodegen generate`.

## Checks that run without Xcode
- Logic: `cd ios/DailyAgent && swiftc -swift-version 5 Sources/Models.swift Sources/Format.swift Checks/main.swift -o /tmp/ios_checks && /tmp/ios_checks`
- The models decode the real `/today`, `/transactions`, `/banks` and `/goal/today` responses.
