"""The browser the agent drives (spec 13). The real one is a Kernel cloud browser, reached only
through the guarded HTTP client. Every page script here is a fixed template: the model never sends
code, only coordinates, keys and text."""

import json
from typing import Protocol

API = "https://api.onkernel.com"
VIEWPORT = {"width": 1280, "height": 800}

# reads the page and the element under a point (or the focused element) straight from the browser
INSPECT = """
const pt = %s;
const r = await page.evaluate((pt) => {
  const el = pt ? document.elementFromPoint(pt[0], pt[1]) : document.activeElement;
  const t = (el && el.closest('button,a,input,select,textarea,[role=button],[role=link]')) || el;
  const clean = s => (s || '').replace(/\\s+/g, ' ').trim().slice(0, 120);
  const body = document.body ? document.body.innerText.slice(0, 20000) : '';
  const heads = [document.title, ...[...document.querySelectorAll('h1,h2')].slice(0, 4).map(h => h.innerText)].join(' ');
  return {
    element: t ? {
      tag: t.tagName.toLowerCase(), type: (t.getAttribute('type') || '').toLowerCase(),
      role: t.getAttribute('role') || '', text: clean(t.innerText || t.value || ''),
      aria: clean(t.getAttribute('aria-label') || t.getAttribute('title') || ''),
      in_form: !!t.closest('form'), password: (t.type || '') === 'password',
    } : null,
    timed: /time remaining|time limit|timer|proctor|lockdown browser|respondus/i.test(body)
        || /\\b(quiz|quizzes|exam|midterm|final exam|test)\\b/i.test(heads),
    captcha: !!document.querySelector('iframe[src*=recaptcha],iframe[src*=hcaptcha],iframe[src*=turnstile],.g-recaptcha,.h-captcha,.cf-turnstile')
        || /verify you are human|i'?m not a robot/i.test(body),
  };
}, pt);
return { ...r, url: page.url() };
"""
GOTO = "await page.goto(%s, { waitUntil: 'domcontentloaded', timeout: 30000 }); return page.url();"


class Driver(Protocol):
    def start(self, start_url: str) -> str: ...  # returns the live view URL
    def screenshot(self) -> bytes: ...
    def inspect(self, x: int | None = None, y: int | None = None) -> dict: ...
    def click(self, x: int, y: int) -> None: ...
    def type_text(self, text: str) -> None: ...
    def press_key(self, keys: list[str]) -> None: ...
    def scroll(self, x: int, y: int, dy: int) -> None: ...
    def goto(self, url: str) -> None: ...
    def stop(self) -> None: ...


class KernelDriver:
    """One Kernel browser per session, loaded from a profile used only for school sites, so you
    sign in yourself once in the live view and later sessions stay signed in."""

    def __init__(self, http, api_key: str, profile: str):
        self.http, self.key, self.profile, self.id = http, api_key, profile, None

    def _call(self, method: str, path: str, **kw):
        r = self.http.request(
            "kernel", method, API + path, headers={"Authorization": f"Bearer {self.key}"}, **kw
        )
        r.raise_for_status()
        return r

    def _run(self, code: str):
        j = self._call(
            "POST",
            f"/browsers/{self.id}/playwright/execute",
            json={"code": code, "timeout_sec": 45},
        ).json()
        if not j.get("success"):
            raise RuntimeError("browser script failed")  # never echo page text or errors into logs
        return j.get("result")

    def start(self, start_url: str) -> str:
        r = self.http.request(
            "kernel",
            "POST",
            API + "/profiles",
            headers={"Authorization": f"Bearer {self.key}"},
            json={"name": self.profile},
        )
        if r.status_code not in (200, 201, 409):  # 409: the profile already exists, which is fine
            r.raise_for_status()
        b = self._call(
            "POST",
            "/browsers",
            json={
                "profile": {"name": self.profile, "save_changes": True},
                "timeout_seconds": 900,  # idle time before Kernel ends it: room to sign in
                "viewport": VIEWPORT,
                "start_url": start_url,
            },
        ).json()
        self.id = b["session_id"]
        lv = self._call(
            "POST", f"/browsers/{self.id}/live_view", json={"scope": "control", "ttl_seconds": 3600}
        ).json()
        return lv["url"]

    def screenshot(self) -> bytes:
        return self._call("POST", f"/browsers/{self.id}/computer/screenshot", json={}).content

    def inspect(self, x=None, y=None) -> dict:
        pt = json.dumps([int(x), int(y)]) if x is not None and y is not None else "null"
        return self._run(INSPECT % pt) or {}

    def click(self, x, y):
        self._call(
            "POST", f"/browsers/{self.id}/computer/click_mouse", json={"x": int(x), "y": int(y)}
        )

    def type_text(self, text):
        self._call("POST", f"/browsers/{self.id}/computer/type", json={"text": text})

    def press_key(self, keys):
        self._call("POST", f"/browsers/{self.id}/computer/press_key", json={"keys": list(keys)})

    def scroll(self, x, y, dy):
        self._call(
            "POST",
            f"/browsers/{self.id}/computer/scroll",
            json={"x": int(x), "y": int(y), "delta_y": int(dy)},
        )

    def goto(self, url):
        self._run(GOTO % json.dumps(url))

    def stop(self):
        if self.id:
            self._call("DELETE", f"/browsers/{self.id}")  # also kills the live view link
            self.id = None
