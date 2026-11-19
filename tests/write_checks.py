"""Static scanners used by the spec 17 tests."""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCOPE_RE = re.compile(r"https://www\.googleapis\.com/auth/[\w./-]+")
HTTP_LIBS = {
    "httpx",
    "requests",
    "urllib3",
    "aiohttp",
    "http.client",
    "urllib.request",
    "googleapiclient",
    "google.auth.transport",
    "httpcore",
    "socket",
}
HTTP_LEAVES = {"httpx", "requests", "httpcore", "aiohttp"}  # catches `from app.x import httpx`
WRITE_PATTERNS = [
    r"\.events\(\)\.(insert|patch|update|delete|import_|move|quickAdd)",
    r"\.messages\(\)\.(send|modify|trash|delete|insert|import_)",
    r"\.drafts\(\)\.(create|send|update|delete)",
    r"\bgit\s+(commit|push)\b",
    r"[\"'](commit|push)[\"']",
    r"\.(commit|push)\(\s*\)\s*#?\s*git",
    r"(payments?|transfers?)/(create|initiate|submit)",
    r"\bgit\.(Repo|cmd)",
]


def py_files(*dirs: str):
    for d in dirs:
        yield from (ROOT / d).rglob("*.py")


def unlisted_scopes(text: str, allowed) -> set[str]:
    return {m for m in SCOPE_RE.findall(text) if m not in allowed}


def imports_of(source: str) -> set[str]:
    found = set()
    for n in ast.walk(ast.parse(source)):
        if isinstance(n, ast.Import):
            found |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            found.add(n.module)
            found |= {f"{n.module}.{a.name}" for a in n.names}
    return found


def http_imports(source: str) -> set[str]:
    return {
        i
        for i in imports_of(source)
        if any(i == h or i.startswith(h + ".") for h in HTTP_LIBS)
        or i.rsplit(".", 1)[-1] in HTTP_LEAVES
    }


def write_calls(text: str) -> list[str]:
    return [p for p in WRITE_PATTERNS if re.search(p, text)]
