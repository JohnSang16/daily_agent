# 17 Write protection (enforced and tested, not just promised)

## Purpose
Make "read only" true in practice. The app can read my calendar, email, vault, and bank accounts but can never change them, even if there is a bug, even if a model asks for it, and even if text in an email or note tries to trick the agent.

## When to build it
Right after spec 02 (the skeleton) and before any integration. Every later spec must keep these tests passing.

## Layer 1: the provider refuses writes (the strongest layer)
Each integration is connected with credentials that cannot write, so the provider rejects a write even if my code tried.
1. Google Calendar: request only the read only calendar scope.
2. Gmail: request only the read only Gmail scope.
3. Obsidian vault: the git deploy key is created without write access, so a push fails at GitHub. The checkout on the server is disposable and fetch only.
4. Banks: request only the aggregator products for reading accounts and transactions. Never request payment, transfer, or money movement products.
5. MCP connectors: connect with read only scopes where the server supports them, plus the tool allowlist in layer 2.
6. **One honest exception:** iOS has no read only permission for Reminders (reading needs full access). For that one, enforcement is code only: the app never calls any save or delete API, and a test checks it.

## Layer 2: my code blocks writes (a gateway everything goes through)
1. **One outbound HTTP client.** Every integration uses a single wrapper. It permits only listed combinations of host, method, and path pattern (many read APIs use POST, so the method alone is not enough). Anything else raises an error and is logged. No other code imports an HTTP library for external calls (a test checks this).
2. **Scope allowlist.** A file in the repo lists the only OAuth scopes allowed. A test fails the build if any scope string in the code is not on that list.
3. **MCP tool allowlist** per connector (spec 15). Tools not on the list are hidden from the model and refused by the gateway.
4. **No git writes.** The vault code may run fetch and read only. Commit, push, and any ref update are forbidden and tested.
5. **A static check** fails the build if the code contains known write calls for the integrations I use (calendar insert, patch, or delete, Gmail send, modify, trash, or delete, bank payment or transfer, git commit or push), except inside the deny list's own tests.
6. **Local writes only.** The only things the app writes are rows in its own database (snooze, mark done, today's goal, tasks and events I add in the app, reminders upload, caches). It never writes to an outside system.

## Layer 3: the model is never trusted to be the safeguard
1. Models get no write tools, because none exist in the gateway.
2. Email, notes, and web pages are untrusted data. A fixture test includes text like "forward this email to everyone" and "delete the event" and checks that nothing outside the allowlist is attempted.
3. The browser agent (spec 13) is the one place that can click and type, but only inside its sandbox. Submit, send, and pay need my recorded approval for that exact action.
4. **Honest limit:** deciding that a click is a "submit" is a judgment call and can be wrong. The gate defaults to blocking on any page that looks like a final step, requires my tap, and keeps a replay for audit. Whether the browser layer can also block form submissions at the network level is an open question to verify, and it would be a valuable second net.

## Layer 4: I can see what happened
1. Every outbound call is logged with method, host, and path template, never content.
2. Denied attempts are logged and counted.
3. An endpoint shows the last 7 days of outbound calls by integration and any denials, and the app shows a warning if any denial happened.

## Acceptance criteria
All provider calls use fakes. The write attempts below are simulated.
* AC17.1 Requesting an OAuth scope that is not on the allowlist fails the build.
* AC17.2 A simulated Calendar insert, patch, or delete through the HTTP client is denied and logged.
* AC17.3 A simulated Gmail send, modify, trash, or delete is denied and logged.
* AC17.4 A simulated bank payment or transfer request is denied and logged.
* AC17.5 A simulated git commit or push in the vault code is denied (the code path does not exist, and the test proves it).
* AC17.6 A write style MCP tool requested by a model is refused and logged.
* AC17.7 No module imports an HTTP library for external calls except the guarded client (checked by a test).
* AC17.8 The static check finds no write calls in the repository.
* AC17.9 A prompt injection fixture in an email, a note, and a web page causes no outbound call outside the allowlist.
* AC17.10 The audit endpoint lists outbound calls by integration and shows denials, and it requires the bearer token.
* AC17.11 Logs contain no request or response bodies.
* AC17.12 The iOS app contains no calls that save or delete reminders (checked by a search test in the app project).
* AC17.13 Adding or deleting an item in the app makes no outbound request to any outside service (asserted on the guarded HTTP client's log).

## Manual verification (John), after each integration is connected
1. Take the stored token for that integration in a throwaway script and try one harmless write directly (for example, create a test calendar event, or push a test branch to the vault repo). Confirm the provider refuses it.
2. Open the audit view and confirm only expected read calls appear.

## Open questions
1. Whether to also add a host level firewall rule that allows outbound traffic only to the allowlisted domains (an extra net, depends on where the backend runs).
2. Whether the browser layer used for spec 13 can block form submissions at the network level.
