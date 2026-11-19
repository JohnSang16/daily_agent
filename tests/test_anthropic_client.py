import json

import httpx
import pytest

from app.allowlist import RULES
from app.config import Settings
from app.http_client import GuardedHttpClient, RequestDenied
from app.llm.anthropic_client import AnthropicClient
from app.main import create_app


class Sink:
    def __init__(self):
        self.rows = []

    def record(self, *a, **k):
        self.rows.append(a)


def client_with(handler):
    http = GuardedHttpClient(Sink(), rules=RULES, transport=httpx.MockTransport(handler))
    return AnthropicClient(http, "sk-ant-TESTKEY", "model-from-settings")


def test_sends_prompt_without_tools_and_parses_usage():
    seen = {}

    def handler(req):
        seen["req"], seen["body"] = req, json.loads(req.content)
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": " Start with Essay. "}],
                "usage": {"input_tokens": 12, "output_tokens": 5},
            },
        )

    r = client_with(handler).complete("PROMPT")
    assert (r.text, r.input_tokens, r.output_tokens) == ("Start with Essay.", 12, 5)
    assert seen["req"].headers["x-api-key"] == "sk-ant-TESTKEY"
    assert seen["body"]["model"] == "model-from-settings"
    assert seen["body"]["messages"] == [{"role": "user", "content": "PROMPT"}]
    assert "tools" not in seen["body"] and seen["body"]["max_tokens"] <= 500
    assert seen["body"]["thinking"] == {"type": "disabled"}


def test_http_error_raises_without_leaking_key():
    c = client_with(lambda req: httpx.Response(401, json={"error": "bad"}))
    with pytest.raises(httpx.HTTPStatusError) as e:
        c.complete("x")
    assert "sk-ant-TESTKEY" not in str(e.value)


def test_allowlist_only_permits_messages_post():
    http = GuardedHttpClient(
        Sink(), rules=RULES, transport=httpx.MockTransport(lambda r: httpx.Response(200))
    )
    with pytest.raises(RequestDenied):
        http.request("anthropic", "GET", "https://api.anthropic.com/v1/models")
    with pytest.raises(RequestDenied):
        http.request("anthropic", "POST", "https://api.anthropic.com/v1/files")


def _app(**kw):
    s = Settings(_env_file=None, api_token="tok", database_url="sqlite://", **kw)
    return create_app(s)


def test_wired_only_when_key_and_model_set():
    assert _app().state.llm is None
    assert _app(anthropic_api_key="sk-ant-x").state.llm is None  # no model: stay on template
    assert isinstance(_app(anthropic_api_key="sk-ant-x", llm_model="m").state.llm, AnthropicClient)


def test_cut_off_response_is_a_failure():
    c = client_with(
        lambda req: httpx.Response(
            200,
            json={
                "stop_reason": "max_tokens",
                "content": [{"type": "text", "text": "half a sen"}],
                "usage": {"input_tokens": 1, "output_tokens": 400},
            },
        )
    )
    with pytest.raises(ValueError):
        c.complete("x")
