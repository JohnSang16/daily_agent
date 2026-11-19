"""Fixes from the strongest-model security review of spec 17 (2026-11-19)."""

import json
import logging
import sys

import httpx
import pytest

from app.allowlist import RULES
from app.config import Settings
from app.http_client import GuardedHttpClient, RequestDenied, templatize
from app.logging_config import RedactionFilter
from tests import write_checks as wc

CAL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
MSG = "https://api.anthropic.com/v1/messages"


class Rec:
    def __init__(self):
        self.rows = []

    def record(self, *a, **k):
        self.rows.append(a)


@pytest.fixture
def sent():
    return []


@pytest.fixture
def guard(sent):
    def handler(req):
        sent.append(req)
        return httpx.Response(307, headers={"location": "https://evil.example/x"})

    return GuardedHttpClient(Rec(), rules=RULES, transport=httpx.MockTransport(handler))


def test_1_follow_redirects_cannot_be_turned_on(guard, sent):
    with pytest.raises(RequestDenied):
        guard.request(
            "anthropic",
            "POST",
            MSG,
            json={"model": "m", "max_tokens": 1, "messages": []},
            follow_redirects=True,
        )
    assert sent == []
    r = guard.request(
        "anthropic", "POST", MSG, json={"model": "m", "max_tokens": 1, "messages": []}
    )
    assert r.status_code == 307 and len(sent) == 1  # normal calls still work, hop not followed


@pytest.mark.parametrize(
    "url",
    [
        "https://www.googleapis.com/calendar/v3/../../gmail/v1/users/me/settings/x",
        "https://www.googleapis.com/calendar/v3/calendars/%2e%2e/%2e%2e/gmail/v1/users/me",
        "https://www.googleapis.com/calendar/v3/calendars/a%2fb/events",
    ],
)
def test_2_dot_segments_and_encoded_slashes_denied(guard, sent, url):
    with pytest.raises(RequestDenied):
        guard.request("google_calendar", "GET", url)
    assert sent == []


def test_3_inner_client_cannot_skip_the_guard(guard, sent):
    with pytest.raises(RequestDenied):
        guard._http.post("https://evil.example/x")
    assert sent == []


def test_3_checker_flags_reexported_and_low_level_http_imports():
    assert wc.http_imports("from app.http_client import httpx")
    assert wc.http_imports("import httpcore")
    assert wc.http_imports("import socket")
    assert not wc.http_imports("import json")


def _msg(guard, body=None, headers=None):
    body = body or {"model": "m", "max_tokens": 1, "messages": [{"role": "user", "content": "x"}]}
    return guard.request("anthropic", "POST", MSG, json=body, headers=headers or {})


def test_4_anthropic_body_is_limited(guard, sent):
    _msg(guard)
    for extra in ({"tools": []}, {"mcp_servers": []}, {"container": {}}):
        with pytest.raises(RequestDenied):
            _msg(guard, {"model": "m", "max_tokens": 1, "messages": [], **extra})
    with pytest.raises(RequestDenied):
        _msg(guard, headers={"anthropic-beta": "mcp-client-2025-04-04"})
    assert len(sent) == 1
    assert json.loads(sent[0].content)["model"] == "m"


@pytest.mark.parametrize("h", ["X-HTTP-Method-Override", "x-method-override", "X-HTTP-Method"])
def test_5_method_override_headers_denied(guard, sent, h):
    with pytest.raises(RequestDenied):
        guard.request("google_calendar", "GET", CAL, headers={h: "DELETE"})
    assert sent == []


def test_6_empty_token_never_authenticates():
    from fastapi.testclient import TestClient

    from app.main import create_app

    s = Settings(_env_file=None, api_token="", database_url="sqlite://")
    c = TestClient(create_app(s, sources={}))
    assert c.get("/today", headers={"Authorization": "Bearer "}).status_code == 401


def test_7_tracebacks_are_redacted():
    h = logging.Handler()
    seen = []
    h.emit = lambda r: seen.append(logging.Formatter().format(r))
    lg = logging.getLogger("t7")
    lg.addHandler(h)
    lg.propagate = False
    h.addFilter(RedactionFilter(["SECRETTOKEN"]))
    try:
        raise RuntimeError("https://x/feed.ics?token=SECRETTOKEN")
    except RuntimeError:
        lg.error("failed", exc_info=sys.exc_info())
    assert seen and "SECRETTOKEN" not in seen[0] and "RuntimeError" in seen[0]


def test_8_audit_hides_names_after_collections():
    assert templatize("/calendar/v3/calendars/family/events") == "/calendar/v3/calendars/:id/events"
    assert templatize("/gmail/v1/users/me/labels/Work") == "/gmail/v1/users/me/labels/:id"
    assert templatize("/gmail/v1/users/me/messages") == "/gmail/v1/users/me/messages"
