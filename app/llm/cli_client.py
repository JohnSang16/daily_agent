"""LLM client that runs headless Claude Code, so calls bill the subscription, not API credits.

Spec 17 exception: this call leaves through the claude CLI, not the guarded HTTP client.
It stays safe because the CLI gets no tools, no MCP servers, no user settings or hooks,
and an empty working dir, so it can only turn text into text.
"""

import json
import os
import subprocess
import tempfile

from app.llm.client import LlmResult

SYSTEM = "Answer the user's message directly. Plain text only."


class ClaudeCliClient:
    def __init__(self, model: str, binary: str = "claude", timeout: int = 90, run=subprocess.run):
        self.model, self.binary, self.timeout, self.run = model, binary, timeout, run

    def complete(self, prompt: str) -> LlmResult:
        # an API key in the env makes the CLI bill the API instead of the subscription
        drop = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
        env = {k: v for k, v in os.environ.items() if k not in drop}
        with tempfile.TemporaryDirectory() as cwd:
            p = self.run(
                [
                    self.binary,
                    "-p",
                    "--model",
                    self.model,
                    "--output-format",
                    "json",
                    "--tools",
                    "",
                    "--strict-mcp-config",
                    "--setting-sources",
                    "project",  # empty cwd, so nothing loads
                    "--disable-slash-commands",
                    "--no-session-persistence",
                    "--system-prompt",
                    SYSTEM,
                ],
                input=prompt,  # stdin, so the prompt never shows up in ps
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=cwd,
                env=env,
            )
        if p.returncode != 0:
            raise RuntimeError(f"claude cli exited {p.returncode}")  # stderr may hold prompt text
        j = json.loads(p.stdout)
        if j.get("is_error") or j.get("subtype") != "success":
            raise RuntimeError(f"claude cli failed: {j.get('subtype')}")
        u = j.get("usage", {})
        return LlmResult(j["result"].strip(), u.get("input_tokens", 0), u.get("output_tokens", 0))
