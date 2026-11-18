"""Per-connector MCP tool allowlist. Write-style tools can never be allowlisted."""

import re

from app.audit import AuditSink

WRITE_VERBS = re.compile(
    r"(send|delete|remove|label|draft|edit|create|update|move|trash|write|post|reply|forward)", re.I
)


class ToolDenied(Exception):
    pass


class ToolAllowlist:
    def __init__(self, allowed: dict[str, set[str]], audit: AuditSink):
        for connector, tools in allowed.items():
            bad = [t for t in tools if WRITE_VERBS.search(t)]
            if bad:
                raise ValueError(f"write-style tools cannot be allowlisted for {connector}: {bad}")
        self.allowed, self.audit = allowed, audit

    def visible(self, connector: str, tools: list[str]) -> list[str]:
        return [t for t in tools if t in self.allowed.get(connector, set())]

    def authorize(self, connector: str, tool: str) -> None:
        if tool not in self.allowed.get(connector, set()):
            self.audit.record(connector, "TOOL", "mcp", tool, False)
            raise ToolDenied(f"{tool} is not allowlisted for {connector}")
        self.audit.record(connector, "TOOL", "mcp", tool, True)
