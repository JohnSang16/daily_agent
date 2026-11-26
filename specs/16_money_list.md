# 16 Money: a plain list of transactions, with the bank

## Purpose
A Money screen that shows my transactions as a simple list, each with the bank it came from, like Rocket Money's activity list but without charts, budgets, or totals. It is read only.

## Gate
Specs 02, 03, 08, and 09 are done, and spec 10 (the app) exists. A security review of token storage is done before real bank data is connected (see Security).

## What the screen shows
1. A large light title ("Money") with the month under it, then one chip that filters by bank ("banks: all"), then the list.
2. The list is grouped by day (today, yesterday, then the weekday and date). Each transaction has two lines on the left (merchant on top, then bank, category, and "pending" when it is pending) and the amount on the right.
3. Money out shows as a plain amount. Money in shows with a plus sign. The app uses no minus signs and no colors.
4. Tapping a transaction opens a sheet with merchant, amount, date, bank, category, and status. It is read only.
5. The bank chip opens a sheet to turn individual accounts on or off for the list.
6. Until a bank is connected, the screen shows demo data with a quiet note saying so.

## Data
1. **Aggregator:** a bank data aggregator (Plaid is the likely choice) so the backend never sees bank passwords. Choose after reading current pricing and terms for personal use and for the account types I have. Compare at least one cheaper alternative.
2. **Read only:** only the permissions to read accounts and transactions are requested. No payment, transfer, or money movement permissions are ever requested.
3. **Tables:** `bank_accounts` (id, institution, nickname, last four digits, encrypted token reference) and `transactions` (id, account id, posted date, merchant, amount in cents, direction, category, pending flag, source id). Amounts are stored as integer cents, never floats.
4. **Sync:** pulled on a schedule and by the aggregator's webhook when available. Pending transactions are updated when they post, without creating duplicates.
5. **Categories:** the aggregator's category is used first. An optional LLM step may clean merchant names and categories. It sees only merchant and amount, never account numbers, and respects the token budget.
6. **Retention:** keep what the list needs and let me delete everything from the connectors screen (settings, then connectors).

## Security
1. Access tokens are encrypted at rest and never sent to the phone or to any model.
2. Bank connection is created with the aggregator's own secure flow (their hosted link screen), not by typing credentials into this app.
3. No credentials or account numbers in logs. Log counts and ids only.
4. The agent's ask mode can read transactions only when the calendar and tasks style context for money is turned on for that chat. Money is off by default in every new chat.
5. No write actions of any kind. The system can never move money, pay a bill, or transfer.
6. Before real accounts are connected: encrypted token storage is proven by tests, and I have read the aggregator's terms.

## Acceptance criteria
All aggregator calls use a fake client in tests.
* AC16.1 A fake client with three accounts produces the correct transactions grouped by day, newest first.
* AC16.2 Amounts are stored as integer cents and shown with two decimals and a plus sign for money in.
* AC16.3 A pending transaction that later posts updates the same row and does not duplicate.
* AC16.4 The bank filter shows only transactions from enabled accounts, and the chip label reflects the choice.
* AC16.5 No code path requests or uses payment, transfer, or write permissions (assert on requested scopes).
* AC16.6 Tokens are encrypted at rest and never appear in API responses, logs, or model input.
* AC16.7 Logs contain no merchant names, amounts, or account numbers.
* AC16.8 Deleting a bank connection deletes its tokens and its stored transactions.
* AC16.9 In ask mode, money data is unavailable unless the money context is on for that chat (enforced on the backend).
* AC16.10 With no bank connected, the screen shows demo data with the quiet demo note.
* AC16.11 `GET /transactions` and related endpoints return 401 without the bearer token.
* AC16.12 The list handles 5,000 transactions and renders the first screen in under one second with paging.

## API (bearer token required)
1. `GET /banks` lists connected accounts with status and last sync.
2. `GET /transactions?bank=...&cursor=...` returns a page of transactions, newest first.
3. `POST /banks/connect` starts the aggregator's connection flow. `DELETE /banks/{id}` removes one and deletes its data.

## Money overview (added 2026-11-19 at John's request, replaces part of Out of scope)
The screen is now four views: **overview**, **banks**, **income** and **activity** (the plain list above).
1. `GET /money/summary?months=6` returns income and spend per month, this month's totals and net, spending by category, and holdings (cash, savings, invested, owed on cards, owed on loans, net).
2. Moves between my own accounts (Plaid transfer categories) and credit card payments are not spending or income, except cash withdrawals (`TRANSFER_OUT_WITHDRAWAL`), which are spending. A refund reduces spending. Only the INCOME category counts as income.
3. Account type, subtype and balance are stored per account. Turning an account off removes it from every total.
4. Budget goals: `GET /budgets`, `PUT /budgets/{category}` (limit in cents, above 0), `DELETE /budgets/{category}`. A goal is for one category or TOTAL. Each shows this month's spending against its limit.
5. `GET /transactions?kind=income|spend|all` powers the income log and a spending only list.
* AC16.13 Totals exclude transfers and card payments, and a refund nets against spending.
* AC16.14 Holdings group cash, savings, invested, cards owed and loans owed from the latest balances and leave out turned off accounts.
* AC16.15 Budget limits must be positive, categories must look like Plaid categories, and each goal reports its spending for the current month.
Still out of scope: bills, subscription cancelling, moving money, and any write action.

## Goals tab (added 2026-11-25 at John's request)
Money gets a fifth view, **goals**, after activity. It only reads balances and income, it never moves money.
1. **Stretch goal** at the top: one big income target with a due date and a floor (for example $606,000 earned by 2027-11-25, floor $100,000). Progress is INCOME transactions since the goal's start date. The floor is a quiet mark on the bar.
2. **This month**: the existing budget goals (same data as the overview), shown again here.
3. **Seasons**: goals grouped by due date (end of 2026, end of spring, end of summer). Each goal has a name, a target in cents, a due date and what it tracks: one account's balance, net worth, invested total, or owed on cards (target 0, met when nothing is owed). The current season opens first, later ones are collapsed.
4. Table `savings_goals` (id, name, kind, account id or null, target cents, start date or null, due date, floor cents or null). Kinds: `account`, `net_worth`, `invested`, `cards_owed`, `income_since` (the stretch goal, at most one).
5. API: `GET /money/goals` returns every goal with its current cents and fraction, grouped by due date. `PUT /money/goals/{id}` creates or replaces one, `DELETE /money/goals/{id}` removes it.
* AC16.16 Targets must be positive (0 allowed only for `cards_owed`), the due date is required, and an `account` goal must name an existing account.
* AC16.17 Current amounts come from the latest balances (account, net worth, invested, cards owed) or from INCOME transactions on or after the start date, with turned off accounts left out.
* AC16.18 `GET /money/goals` groups goals by due date, soonest first, and returns 401 without the bearer token.
* AC16.19 Only one `income_since` goal can exist, and its floor must be below its target.

## Decisions (2026-11-19, replacing the open questions)
1. Aggregator: Plaid, free Trial plan (10 live Items) once Production access is approved. Built and tested against Plaid Sandbox first. Real banks wait for me to read Plaid's terms (security rule 6).
2. Banks to connect first: chosen by me later, at connect time.
3. Ask mode: money is a separate context (AC16.9). Changed 2026-11-25 with John's OK: the app's "all" context now includes money, and with money on the model answers from the money summary, this month's budgets, top merchants and up to 40 matching plus 30 recent charges from the last 90 days. Never tokens, account ids or account numbers.
4. Tables: tokens live on a `bank_items` table (one per bank login) and `bank_accounts` points to it, instead of a token reference on each account.
5. Connection flow: Plaid Hosted Link (their own screen, opened from a link), then the backend collects the result. Sandbox also has `POST /banks/sandbox`, which creates a fake bank without any screen.
6. The only Plaid products ever requested are `transactions`. The outbound guard refuses any request body that names another product, and allows only these paths on the Plaid hosts: link token create and get, public token exchange, accounts get, institutions get by id, transactions sync, item remove (disconnects my own link, used by DELETE /banks), plus sandbox public token create on the sandbox host only.
7. The optional LLM clean up step is skipped.

## Open questions
None.
