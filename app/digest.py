"""Read the standing lines for the daily brief from the vault, at request time. Nothing personal
is stored in this repo. Missing files simply leave the field empty."""

import re
from pathlib import Path


def _read(vault_path: str, rel: str) -> str | None:
    if not vault_path:
        return None
    p = Path(vault_path) / rel
    try:
        return p.read_text(errors="replace") if p.is_file() else None
    except OSError:
        return None


def read_lines(vault_path: str) -> dict[str, str]:
    """`_meta/digest-lines.md` holds lines like `MANTRA: ...` and `VISION: ...`."""
    text = _read(vault_path, "_meta/digest-lines.md")
    out: dict[str, str] = {}
    for line in (text or "").splitlines():
        m = re.match(r"^([A-Z]+):\s*(.+)$", line.strip())
        if m:
            out[m.group(1).lower()] = m.group(2).strip()
    return out


def read_why(text: str | None) -> dict | None:
    """The newest `## <date>` entry of `personal/reflections.md`, in John's own words."""
    if not text:
        return None
    body = text.split("\n---", 1)[-1]  # entries live below the header's rule
    entries = re.split(r"(?m)^##\s+", body)[1:]
    for entry in reversed(entries):
        head, _, rest = entry.partition("\n")
        answer = rest.strip()
        if answer:
            m = re.search(r"\d{4}-\d{2}-\d{2}", head)
            return {"date": m.group(0) if m else head.strip(), "text": answer}
    return None


def read_why_from_vault(vault_path: str) -> dict | None:
    return read_why(_read(vault_path, "personal/reflections.md"))


def read_identity(vault_path: str) -> list[str]:
    """Every `IDENTITY:` line in `_meta/digest-lines.md`, in file order, verbatim."""
    text = _read(vault_path, "_meta/digest-lines.md")
    return [m.group(1).strip() for m in re.finditer(r"(?m)^IDENTITY:\s*(.+)$", text or "")]


def read_plan(text: str | None, today: str) -> dict:
    """Items under today's `## YYYY-MM-DD` heading in `personal/today-plan.md`."""
    items: list[dict] = []
    for section in re.split(r"(?m)^##\s+", text or "")[1:]:
        head, _, body = section.partition("\n")
        if head.strip().startswith(today):
            for m in re.finditer(r"(?m)^\s*[-*]\s+\[([ xX])\]\s+(.+)$", body):
                items.append({"text": m.group(2).strip(), "done": m.group(1) in "xX"})
            break
    return {"logged": bool(items), "items": items}


def read_plan_from_vault(vault_path: str, today: str) -> dict:
    return read_plan(_read(vault_path, "personal/today-plan.md"), today)
