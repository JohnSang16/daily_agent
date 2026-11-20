"""The approval gate (spec 13). It judges the element really under the click and the page really
open, as read from the browser, never what the model says it is doing. Page text cannot grant
permission: it only ever makes the gate stricter."""

import hashlib
import json
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

# controls whose name suggests the action hands work in, sends, pays or deletes
SUBMIT = re.compile(
    r"\b(submit|turn\s*in|hand\s*in|send|post|pay|purchase|buy|checkout|finish|finalize|confirm|"
    r"delete|remove|publish|check\s*answer|i'?m\s*done|end\s*(quiz|test|exam))\b",
    re.I,
)
ENTER_KEYS = {"return", "enter", "kp_enter"}


@dataclass(frozen=True)
class Decision:
    verdict: str  # run, approve, block, pause, refuse
    reason: str
    label: str = ""


def host_ok(url: str, allowed: tuple[str, ...]) -> bool:
    """https only, and the host is an allowed domain or one of its subdomains."""
    try:
        u = urlsplit(url)
    except ValueError:
        return False
    host = (u.hostname or "").lower().rstrip(".")
    return u.scheme == "https" and any(host == h or host.endswith("." + h) for h in allowed)


def label_of(el: dict) -> str:
    return " ".join(x for x in (el.get("aria") or "", el.get("text") or "") if x).strip()[:80]


def action_hash(kind: str, page_url: str, label: str, args: dict) -> str:
    """Ties an approval to one action: its type, target, visible label and page (no query)."""
    u = urlsplit(page_url)
    where = f"{u.hostname}{u.path}"
    target = {k: args.get(k) for k in ("x", "y", "keys", "url") if k in args}
    raw = json.dumps([kind, where, label.lower(), target], sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def page_checks(info: dict, allowed: tuple[str, ...]) -> Decision | None:
    """Stops that apply to any action, whatever the element."""
    if info.get("timed"):
        return Decision(
            "refuse", "this looks like a timed, quiz or exam page. the agent never works on those."
        )
    if info.get("captcha"):
        return Decision(
            "pause",
            "there's a bot check on the page. solve it yourself in the live view, then hand back.",
        )
    if not host_ok(info.get("url") or "", allowed):
        return Decision(
            "pause",
            "the page is outside the allowed sites (often a sign in page). "
            "sign in yourself in the live view, then hand back.",
        )
    return None


def decide(kind: str, args: dict, info: dict, allowed: tuple[str, ...]) -> Decision:
    """kind is one of click, type_text, press_key, scroll, open_url. info comes from the browser."""
    if kind == "open_url":
        url = str(args.get("url") or "")
        if not host_ok(url, allowed):
            return Decision("block", "that address is not on the allowed sites.")
        return page_checks(info, allowed) or Decision("run", "", url[:80])
    stop = page_checks(info, allowed)
    if stop:
        return stop
    el = info.get("element") or {}
    label = label_of(el)
    if kind == "click":
        is_submit_button = el.get("in_form") and (
            el.get("type") == "submit"
            or (el.get("tag") == "button" and el.get("type") in (None, "", "submit"))
        )
        if SUBMIT.search(label) or is_submit_button:
            return Decision(
                "approve",
                f'clicking "{label or el.get("tag")}" could hand in or send something.',
                label,
            )
        return Decision("run", "", label)
    if kind == "type_text":
        if el.get("password"):
            return Decision(
                "block", "the agent never types into a password field. you sign in yourself."
            )
        return Decision("run", "", label)
    if kind == "press_key":
        keys = {str(k).lower() for k in args.get("keys") or []}
        if keys & ENTER_KEYS and el.get("in_form"):
            return Decision(
                "approve", "pressing enter in a form could submit it.", label or "enter"
            )
        return Decision("run", "", label)
    if kind == "scroll":
        return Decision("run", "", "")
    return Decision("block", "unknown action.")
