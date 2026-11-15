# 12 Later features (each needs its own full spec before work starts)

## Notifications
A morning briefing push at a chosen time and an alert when a task becomes at risk. Needs the iOS app and a push service. Keep payloads free of private details when possible.

## Money tracking
The plain transaction list is now spec 16. Anything beyond it (budgets, subscriptions, charts) stays here for later. A Rocket Money style view. Use a bank data aggregator (Plaid is the likely choice) so the backend never handles bank passwords. Read only. Prerequisites: spec 10 done, a security review, encrypted token storage proven, transaction categorization approach, and a decision on cost. Never move money.

## Voice
Push to talk, speech to text, the agent, then speech back. Start with Apple's on device speech tools for cost, upgrade only if quality disappoints. The agent answers from `/today` and read only tools. Any voice action that changes data needs a spoken confirmation.

## Browser automation (Kernel or similar)
Only for a source with no API and only after a spec names the exact site and read only task. Never for banks.

## Generic requirements for any later spec
1. A written purpose and acceptance criteria with IDs.
2. Security notes covering new secrets, new scopes, and new data stored.
3. A cost estimate.
4. Updates to `specs/00_principles.md` if a principle must change, with my approval.
