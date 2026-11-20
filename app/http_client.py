"""The single outbound HTTP client. The only module allowed to import an HTTP library.

Every request is checked by an httpx request hook against the exact request httpx will send
(after URL cleanup), so the inner client cannot be used to skip the guard either."""

import json
import re

import httpx

from app.allowlist import RULES, Rule
from app.audit import AuditSink


class RequestDenied(Exception):
    pass


ALLOWED_ARGS = {"params", "headers", "json", "data", "content", "timeout"}
AGENT_BODY_KEYS = {
    "model",
    "max_tokens",
    "system",
    "tools",
    "tool_choice",
    "messages",
    "output_config",
    "fallbacks",
    "cache_control",
}
ANTHROPIC_BODY_KEYS = {"model", "max_tokens", "messages", "thinking", "system"}
COLLECTIONS = {"messages", "threads", "labels", "drafts", "calendars", "events", "feed", "user"}
PLAID_PRODUCT_KEYS = (
    "products",
    "initial_products",
    "optional_products",
    "required_if_supported_products",
    "additional_consented_products",
)
SNEAKY_PATH = re.compile(r"(?i)(^|/)(\.|%2e){1,2}(/|$)|%2f|%5c")


def _is_id(seg: str) -> bool:
    if re.fullmatch(r"v\d+", seg):
        return False
    return len(seg) > 24 or (len(seg) >= 6 and bool(re.search(r"\d", seg)))


def templatize(path: str) -> str:
    """Hide ids and any name that follows a collection, so audit rows carry a template only."""
    out, hide = [], False
    for seg in path.split("/"):
        out.append(":id" if seg and (hide or _is_id(seg)) else seg)
        hide = seg in COLLECTIONS
    return "/".join(out)


class GuardedHttpClient:
    def __init__(self, audit: AuditSink, rules: list[Rule] | None = None, transport=None):
        self.audit, self.rules = audit, RULES if rules is None else rules
        # no redirects: a redirect could hop to a host that is not on the allowlist
        self._http = httpx.Client(
            transport=transport,
            follow_redirects=False,
            timeout=30,
            event_hooks={"request": [self._guard]},
        )

    def _permitted(self, integration: str | None, req: httpx.Request) -> bool:
        if not integration or req.url.scheme != "https":
            return False
        if SNEAKY_PATH.search(req.url.raw_path.decode().split("?")[0]):
            return False
        if any(k.lower().startswith(("x-http-method", "x-method-override")) for k in req.headers):
            return False
        if not any(
            r.integration == integration
            and r.host == req.url.host
            and r.method == req.method
            and re.fullmatch(r.path_regex, req.url.path)
            for r in self.rules
        ):
            return False
        if integration == "anthropic":  # text in, text out: no tools, no connectors, no betas
            if "anthropic-beta" in req.headers:
                return False
            try:
                return set(json.loads(req.content)) <= ANTHROPIC_BODY_KEYS
            except ValueError:
                return False
        if integration == "anthropic_agent":
            return _agent_body_ok(req)
        if integration == "kernel" and req.url.path.endswith("/playwright/execute"):
            return _browser_code_ok(req)
        if integration == "plaid":  # read only: transactions is the only product ever requested
            try:
                body = json.loads(req.content)
            except ValueError:
                return False
            return all(set(body.get(k) or []) <= {"transactions"} for k in PLAID_PRODUCT_KEYS)
        return True

    def _guard(self, req: httpx.Request) -> None:
        if not self._permitted(req.extensions.get("integration"), req):
            raise RequestDenied(
                f"{req.method} {req.url.host}{templatize(req.url.path)} not allowed"
            )

    def request(self, integration: str, method: str, url: str, **kwargs) -> httpx.Response:
        method = method.upper()
        try:
            if set(kwargs) - ALLOWED_ARGS:
                raise RequestDenied("request argument not allowed")
            req = self._http.build_request(
                method, url, extensions={"integration": integration}, **kwargs
            )
        except (RequestDenied, httpx.InvalidURL):
            self.audit.record(integration, method, "", "", False)
            raise RequestDenied(f"{method} request not allowed") from None
        host, tmpl = req.url.host or "", templatize(req.url.path)
        try:
            resp = self._http.send(req)
        except RequestDenied:
            self.audit.record(integration, method, host, tmpl, False)
            raise
        self.audit.record(integration, method, host, tmpl, True, resp.status_code)
        return resp

    def get(self, integration: str, url: str, **kwargs) -> httpx.Response:
        return self.request(integration, "GET", url, **kwargs)


def _agent_body_ok(req: httpx.Request) -> bool:
    """Spec 13: the agent may offer only its own fixed tools: no server tools, MCP or betas."""
    from app.agent.llm import FALLBACK_BETA, TOOL_NAMES

    if req.headers.get("anthropic-beta", FALLBACK_BETA) != FALLBACK_BETA:
        return False
    try:
        body = json.loads(req.content)
    except ValueError:
        return False
    if not set(body) <= AGENT_BODY_KEYS:
        return False
    tools = body.get("tools") or []
    if not tools or any("type" in t or t.get("name") not in TOOL_NAMES for t in tools):
        return False
    return (body.get("tool_choice") or {"type": "auto"}).get("type") in ("auto", "none")


def _browser_code_ok(req: httpx.Request) -> bool:
    """Only the two fixed page scripts may run in the browser, never code from the model."""
    from app.agent.driver import GOTO, INSPECT

    try:
        code = json.loads(req.content).get("code", "")
    except (ValueError, AttributeError):
        return False
    for tmpl, middle in (
        (INSPECT, r"null|\[\d{1,5}, \d{1,5}\]"),
        (GOTO, r'"https://[^"\\]{1,500}"'),
    ):
        head, tail = tmpl.split("%s")
        if (
            code.startswith(head)
            and code.endswith(tail)
            and re.fullmatch(middle, code[len(head) : len(code) - len(tail)])
        ):
            return True
    return False
