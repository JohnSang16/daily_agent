# Plan: spec 17 write protection

Tasks (tied to ACs):
1. app/scopes.py allowlist + test that scans code for unlisted scope strings (AC17.1)
2. app/http_client.py guarded client: host+method+path rules, no redirects, audit, deny raises (AC17.2, 17.3, 17.4, 17.11)
3. app/allowlist.py read-only rules for Google Calendar, Gmail, Google token refresh
4. app/mcp_allowlist.py tool allowlist, refuses write-style tools (AC17.6)
5. static tests: no git writes, no write calls, no HTTP-library imports outside the client (AC17.5, 17.7, 17.8)
6. audit table + migration 0002 + GET /audit/outbound behind bearer (AC17.10)
7. injection fixtures cause zero outbound calls (AC17.9, partial until specs 05/06 exist)

Deferred until their specs exist: AC17.12 (iOS), AC17.13 (in-app add/delete).

New dependencies: httpx moves from dev to runtime. It is the single HTTP library behind the guarded client.
