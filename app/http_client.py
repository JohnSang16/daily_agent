"""The single outbound HTTP client. The only module allowed to import an HTTP library."""

import re
from urllib.parse import urlsplit

import httpx

from app.allowlist import RULES, Rule
from app.audit import AuditSink


class RequestDenied(Exception):
    pass


def _is_id(seg: str) -> bool:
    if re.fullmatch(r"v\d+", seg):
        return False
    return len(seg) > 24 or (len(seg) >= 6 and bool(re.search(r"\d", seg)))


def templatize(path: str) -> str:
    """Replace id-like path segments so audit rows carry a template, not content."""
    return "/".join(":id" if _is_id(seg) else seg for seg in path.split("/"))


class GuardedHttpClient:
    def __init__(self, audit: AuditSink, rules: list[Rule] | None = None, transport=None):
        self.audit, self.rules = audit, RULES if rules is None else rules
        # no redirects: a redirect could hop to a host that is not on the allowlist
        self._http = httpx.Client(transport=transport, follow_redirects=False, timeout=30)

    def request(self, integration: str, method: str, url: str, **kwargs) -> httpx.Response:
        parts = urlsplit(url)
        method = method.upper()
        tmpl = templatize(parts.path)
        ok = parts.scheme == "https" and any(
            r.integration == integration
            and r.host == parts.hostname
            and r.method == method
            and re.fullmatch(r.path_regex, parts.path)
            for r in self.rules
        )
        if not ok:
            self.audit.record(integration, method, parts.hostname or "", tmpl, False)
            raise RequestDenied(f"{method} {parts.hostname}{tmpl} not allowed for {integration}")
        resp = self._http.request(method, url, **kwargs)
        self.audit.record(integration, method, parts.hostname, tmpl, True, resp.status_code)
        return resp

    def get(self, integration: str, url: str, **kwargs) -> httpx.Response:
        return self.request(integration, "GET", url, **kwargs)
