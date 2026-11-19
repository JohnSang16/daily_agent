"""Read-only outbound rules: only these (integration, host, method, path) combos may be called."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    integration: str
    host: str
    method: str
    path_regex: str


def _plaid() -> list[Rule]:
    paths = (
        "/link/token/create",
        "/link/token/get",
        "/item/public_token/exchange",
        "/accounts/get",
        "/institutions/get_by_id",
        "/transactions/sync",
        "/item/remove",
    )
    hosts = ("sandbox.plaid.com", "production.plaid.com")
    rules = [Rule("plaid", h, "POST", p) for h in hosts for p in paths]
    # the fake bank helper exists on the sandbox host only
    return rules + [Rule("plaid", "sandbox.plaid.com", "POST", "/sandbox/public_token/create")]


RULES = [
    Rule("google_calendar", "www.googleapis.com", "GET", r"/calendar/v3/.*"),
    Rule(
        "gmail",
        "www.googleapis.com",
        "GET",
        r"/gmail/v1/users/me/(messages|threads|labels)(/[^/]+)?",
    ),
    Rule("icollege", "gastate.view.usg.edu", "GET", r"/d2l/le/calendar/feed/.*"),
    # the model call is a POST that only reads: text in, text out, no tools
    Rule("anthropic", "api.anthropic.com", "POST", r"/v1/messages"),
    *_plaid(),
    # token refresh is a POST but only talks to Google's token endpoint
    Rule("google_oauth", "oauth2.googleapis.com", "POST", r"/token"),
]
