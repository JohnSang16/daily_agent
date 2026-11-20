"""Spec 13 solver: the model ladder behind the agent's solve tool, with a fake HTTP client."""

import json
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import select

from app.agent.solver import Solver, same
from app.allowlist import RULES
from app.config import Settings
from app.db import Base, make_session_factory
from app.http_client import GuardedHttpClient, RequestDenied
from app.models import LlmUsage

LADDER = "gemini-a,gemini-b,claude-c,claude-d"


class FakeHttp:
    """answers: model -> answer text, or an int status for a failure."""

    def __init__(self, answers):
        self.answers, self.calls = answers, []

    def request(self, integration, method, url, **kw):
        body = kw["json"]
        model = body["model"]
        self.calls.append((integration, model, json.dumps(body)))
        a = self.answers.get(model, 503)
        if isinstance(a, int):
            return httpx.Response(a, json={"error": {"message": "busy"}})
        if integration == "gemini":
            data = {
                "steps": [
                    {"type": "thought"},
                    {"type": "model_output", "content": [{"type": "text", "text": a}]},
                ],
                "usage": {"total_input_tokens": 40, "total_output_tokens": 3},
            }
        else:
            data = {
                "content": [{"type": "text", "text": a}],
                "usage": {"input_tokens": 40, "output_tokens": 3},
            }
        return httpx.Response(200, json=data)


@pytest.fixture
def sf():
    f = make_session_factory("sqlite://")
    Base.metadata.create_all(f.kw["bind"])
    return f


def solver(sf, answers):
    st = Settings(
        _env_file=None,
        api_token="t",
        database_url="sqlite://",
        gemini_api_key="g",
        anthropic_api_key="a",
        solver_models=LADDER,
    )
    http = FakeHttp(answers)
    clock = type("C", (), {"now": lambda self: datetime(2026, 11, 20, tzinfo=UTC)})()
    return Solver(http, st, sf, clock), http


def models(http):
    return [m for _, m, _ in http.calls]


def test_same_compares_numbers_within_one_percent_and_text_loosely():
    assert same("6 N", "6.0 N") and same("3.2e5 m/s", "3.2×10^5 m/s") and same("1.00 J", "1.009")
    assert not same("6 N", "6.2 N") and not same("6 N", "-6 N")
    assert same(" (B) Increases ", "(b) increases") and not same("increases", "decreases")


def test_AC13_17_answer_only_when_two_rungs_agree(sf):
    s, http = solver(sf, {"gemini-a": "6 N", "gemini-b": "6.0 N"})
    r = s.solve("A 2 kg mass accelerates at 3 m/s^2. Net force?", attempt=0, wrong=[])
    assert r == "answer: 6 N (2 models agree)" and models(http) == ["gemini-a", "gemini-b"]
    assert http.calls[0][0] == "gemini"


def test_AC13_17_whole_ladder_disagrees(sf):
    s, _ = solver(sf, {"gemini-a": "1", "gemini-b": "2", "claude-c": "3", "claude-d": "4"})
    r = s.solve("p", attempt=0, wrong=[])
    assert r.startswith("no agreement") and "ask_john" in r


def test_AC13_17_third_rung_breaks_a_tie(sf):
    s, http = solver(sf, {"gemini-a": "6 N", "gemini-b": "7 N", "claude-c": "7.0 N"})
    assert s.solve("p", attempt=0, wrong=[]) == "answer: 7 N (2 models agree)"
    assert http.calls[2][0] == "anthropic"  # the plain text lane: no tools


def test_AC13_18_busy_or_failing_rungs_are_skipped(sf):
    s, http = solver(sf, {"gemini-a": 503, "gemini-b": "6 N", "claude-c": 500, "claude-d": "6 N"})
    assert s.solve("p", attempt=0, wrong=[]) == "answer: 6 N (2 models agree)"
    assert models(http) == LADDER.split(",")


def test_AC13_19_repeat_starts_higher_and_skips_wrong_answers(sf):
    s, http = solver(sf, {"gemini-b": "6 N", "claude-c": "8 N", "claude-d": "8 N"})
    assert s.solve("p", attempt=1, wrong=["6 N"]) == "answer: 8 N (2 models agree)"
    assert "gemini-a" not in models(http)
    assert "6 N" in http.calls[0][2]  # the wrong answer is named so the model avoids it


def test_AC13_19_third_attempt_is_refused(sf):
    s, http = solver(sf, {"gemini-a": "6 N", "gemini-b": "6 N"})
    r = s.solve("p", attempt=2, wrong=["6 N", "7 N"])
    assert "ask_john" in r and http.calls == []


def test_AC13_21_every_call_writes_a_usage_row(sf):
    s, _ = solver(sf, {"gemini-a": 503, "gemini-b": "6 N", "claude-c": "6 N"})
    s.solve("p", attempt=0, wrong=[])
    with sf() as db:
        rows = list(db.scalars(select(LlmUsage)))
    assert [r.model for r in rows] == ["gemini-a", "gemini-b", "claude-c"]
    assert all(r.purpose == "homework_solver" for r in rows) and rows[1].input_tokens == 40


@pytest.fixture
def guard():
    class Rec:
        def record(self, *a, **k):
            pass

    sent = []

    def handler(req):
        sent.append(req)
        return httpx.Response(200, json={})

    return GuardedHttpClient(Rec(), rules=RULES, transport=httpx.MockTransport(handler)), sent


def test_AC13_20_gemini_lane_allows_only_model_and_input(guard):
    g, sent = guard
    url = "https://generativelanguage.googleapis.com/v1beta/interactions"
    g.request("gemini", "POST", url, json={"model": "gemini-a", "input": "p"})
    for bad_url, body in [
        (url, {"model": "m", "input": "p", "tools": [{"type": "code_execution"}]}),
        (url, {"model": "m", "input": ["not", "text"]}),
        ("https://generativelanguage.googleapis.com/v1beta/files", {"model": "m", "input": "p"}),
        ("https://evil.example/v1beta/interactions", {"model": "m", "input": "p"}),
    ]:
        with pytest.raises(RequestDenied):
            g.request("gemini", "POST", bad_url, json=body)
    assert len(sent) == 1


def test_a_reply_with_working_is_judged_on_its_final_line(sf):
    worked = (
        "Acceleration a = 27 m/s ÷ 9.0 s = 3.0 m/s², so F = ma = 1500 kg × 3.0 m/s² = 4500 N.\n\n"
        "**4500 N (4.5 × 10³ N)**"
    )
    s, _ = solver(sf, {"gemini-a": worked, "gemini-b": "4500 N"})
    assert s.solve("p", attempt=0, wrong=[]) == "answer: 4500 N (4.5 × 10³ N) (2 models agree)"
