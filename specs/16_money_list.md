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

## Out of scope
Budgets, charts, totals, bills, subscription cancelling, net worth, moving money, and any write action.

## Open questions
1. Which aggregator, based on current pricing and terms for one personal user.
2. Which banks and cards to connect first.
3. Whether to add a money context toggle to ask mode right away or wait until the list is trusted.
