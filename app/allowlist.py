"""Read-only outbound rules: only these (integration, host, method, path) combos may be called."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    integration: str
    host: str
    method: str
    path_regex: str


RULES = [
    Rule("google_calendar", "www.googleapis.com", "GET", r"/calendar/v3/.*"),
    Rule(
        "gmail",
        "www.googleapis.com",
        "GET",
        r"/gmail/v1/users/me/(messages|threads|labels)(/[^/]+)?",
    ),
    # token refresh is a POST but only talks to Google's token endpoint
    Rule("google_oauth", "oauth2.googleapis.com", "POST", r"/token"),
]
