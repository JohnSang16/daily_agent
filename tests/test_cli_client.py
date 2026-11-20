import json
import subprocess

import pytest

from app.config import Settings
from app.llm.cli_client import ClaudeCliClient
from app.main import create_app


def fake_run(seen, out=None, code=0):
    def run(cmd, **kw):
        seen["cmd"], seen["kw"] = cmd, kw
        body = out or {
            "subtype": "success",
            "is_error": False,
            "result": " Start with Essay. ",
            "usage": {"input_tokens": 12, "output_tokens": 5},
        }
        return subprocess.CompletedProcess(cmd, code, json.dumps(body), "secret prompt text")

    return run


def test_runs_toolless_and_parses_usage(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-LEAK")
    seen = {}
    r = ClaudeCliClient("claude-haiku-5-5", run=fake_run(seen)).complete("PROMPT")
    assert (r.text, r.input_tokens, r.output_tokens) == ("Start with Essay.", 12, 5)
    cmd = seen["cmd"]
    assert cmd[cmd.index("--tools") + 1] == ""  # no tools: text in, text out
    assert "--strict-mcp-config" in cmd and "PROMPT" not in cmd
    assert seen["kw"]["input"] == "PROMPT"
    assert "ANTHROPIC_API_KEY" not in seen["kw"]["env"]  # would bill the API instead


@pytest.mark.parametrize(
    "out,code", [(None, 1), ({"subtype": "error_max_turns", "is_error": True}, 0)]
)
def test_failures_raise_without_leaking_stderr(out, code):
    with pytest.raises(RuntimeError) as e:
        ClaudeCliClient("m", run=fake_run({}, out, code)).complete("x")
    assert "secret prompt text" not in str(e.value)


def test_wired_when_backend_is_cli():
    s = Settings(
        _env_file=None, api_token="t", database_url="sqlite://", llm_backend="cli", llm_model="m"
    )
    assert isinstance(create_app(s).state.llm, ClaudeCliClient)
