"""The agent loop (spec 13). One step is one model call, then each tool call goes through the gate.
Anything that could hand work in waits for John's approval, which is single use and tied to the
exact action. Live view URLs, page text and typed text never reach logs or step summaries."""

import base64
import logging
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.agent.gate import action_hash, decide, page_checks
from app.models import AgentSession, AgentStep, Approval, LlmUsage

log = logging.getLogger("agent")
PURPOSE = "homework_agent"
APPROVAL_MINUTES = 10
ACTIONS = {"click", "type_text", "press_key", "scroll", "open_url"}


@dataclass
class Live:
    """In memory only: the browser, the conversation and the live view link."""

    id: int
    driver: object
    live_view_url: str | None
    messages: list = field(default_factory=list)
    results: list = field(default_factory=list)  # tool results waiting to go back to the model
    notes: list = field(default_factory=list)  # John's messages waiting to go to the model
    pending: dict | None = None  # the tool call held for approval
    lock: threading.Lock = field(default_factory=threading.Lock)


class Agent:
    def __init__(self, session_factory, settings, llm, clock, driver_factory):
        self.sf, self.st, self.llm, self.clock = session_factory, settings, llm, clock
        self.driver_factory = driver_factory
        self.live: dict[int, Live] = {}
        self.allowed = tuple(
            h.strip().lower() for h in settings.agent_allowed_hosts.split(",") if h.strip()
        )

    # ---------- bookkeeping ----------

    def _now(self) -> datetime:
        return self.clock.now()

    def step_log(self, db, sid: int, kind: str, summary: str) -> None:
        db.add(AgentStep(session_id=sid, at=self._now(), kind=kind, summary=summary[:300]))

    def set_status(
        self, sid: int, status: str, reason: str | None = None, kind: str = "status"
    ) -> None:
        with self.sf() as db:
            s = db.get(AgentSession, sid)
            s.status, s.reason = status, reason
            if status == "ended":
                s.ended_at = self._now()
            if reason:
                self.step_log(db, sid, kind, reason)
            db.commit()

    def _daily_used(self, db) -> int:
        tz = ZoneInfo(self.st.user_timezone)
        midnight = datetime.combine(self._now().astimezone(tz).date(), time(), tz).astimezone(UTC)
        return db.scalar(
            select(
                func.coalesce(func.sum(LlmUsage.input_tokens + LlmUsage.output_tokens), 0)
            ).where(LlmUsage.at >= midnight, LlmUsage.purpose == PURPOSE)
        )

    def _limit_hit(self, db, s: AgentSession) -> str | None:
        if s.steps >= self.st.agent_max_steps:
            return f"step limit reached ({self.st.agent_max_steps}). hand back to keep going."
        if self._now() - s.started_at > timedelta(minutes=self.st.agent_max_minutes):
            return f"time limit reached ({self.st.agent_max_minutes} min). hand back to keep going."
        if s.input_tokens + s.output_tokens >= self.st.agent_session_token_budget:
            return "this session's token budget is used up."
        if self._daily_used(db) >= self.st.agent_daily_token_budget:
            return "today's homework agent token budget is used up."
        return None

    # ---------- lifecycle ----------

    def start(self, task_id: int, title: str, site: str, start_url: str) -> int:
        with self.sf() as db:
            s = AgentSession(
                task_id=task_id, title=title, site=site, status="starting", started_at=self._now()
            )
            db.add(s)
            db.commit()
            sid = s.id
        driver = self.driver_factory()
        try:
            url = driver.start(start_url)
        except Exception:
            log.warning("browser could not start")
            self.set_status(sid, "ended", "the browser could not start.")
            raise
        live = Live(sid, driver, url)
        self.live[sid] = live
        shot = self._shot(live)
        # minimal data in: only the assignment title and where to start
        live.messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Assignment: {title}\nSite: {site}\nHere is the browser now.",
                    },
                    *shot,
                ],
            }
        )
        self.set_status(sid, "running", "started. watch it in the live view.", kind="start")
        return sid

    def stop(self, sid: int, reason: str = "stopped. the browser was deleted.") -> None:
        live = self.live.pop(sid, None)
        if live:
            try:
                live.driver.stop()  # deletes the browser, which invalidates the live view link
            except Exception:
                log.warning("browser stop failed")
        self.set_status(sid, "ended", reason, kind="stop")

    def pause(self, sid: int, status: str = "paused", reason: str = "paused by you.") -> None:
        self.set_status(sid, status, reason)

    def handback(self, sid: int) -> None:
        live = self.live.get(sid)
        if live and not live.pending:
            if not live.results:  # after a takeover the model needs to see what changed
                live.notes.append(
                    "John handed control back. Take a screenshot first, the page may have changed."
                )
            self.set_status(sid, "running", "handed back to the agent.")

    def message(self, sid: int, text: str) -> None:
        live = self.live.get(sid)
        if live:
            live.notes.append("Message from John: " + text[:1000])
            with self.sf() as db:
                self.step_log(db, sid, "you", "you sent a message.")
                db.commit()

    # ---------- approvals ----------

    def decide_approval(self, sid: int, aid: int, approve: bool) -> str:
        live = self.live.get(sid)
        with self.sf() as db:
            a = db.get(Approval, aid)
            if a is None or a.session_id != sid:
                return "not_found"
            if a.status != "pending":
                return a.status
            if a.expires_at < self._now():
                a.status = "expired"
                db.commit()
                return "expired"
            a.status, a.decided_at = ("approved" if approve else "denied"), self._now()
            db.commit()
        if not live or not live.pending or live.pending["approval_id"] != aid:
            return "approved" if approve else "denied"
        with live.lock:
            return self._apply_decision(live, aid, approve)

    def _apply_decision(self, live: Live, aid: int, approve: bool) -> str:
        sid = live.id
        if not approve:
            self._result(
                live,
                live.pending["tool_use_id"],
                "John denied this action. Do not try it again. Use ask_john if you need him.",
            )
            live.pending = None
            self.set_status(
                sid, "paused", "you denied it. nothing was submitted. hand back when ready."
            )
            return "denied"
        return self._run_approved(live, aid)

    def _run_approved(self, live: Live, aid: int) -> str:
        p = live.pending
        info = self._inspect(live, p["kind"], p["args"])
        d = decide(p["kind"], p["args"], info, self.allowed)
        h = action_hash(p["kind"], info.get("url") or "", d.label, p["args"])
        with self.sf() as db:
            a = db.get(Approval, aid)
            if a.status != "approved" or h != a.action_hash or d.verdict not in ("approve", "run"):
                a.status = "used"
                db.commit()
                self._result(
                    live,
                    p["tool_use_id"],
                    "The page changed before the approved action ran, so it did not run.",
                )
                live.pending = None
                self.set_status(
                    live.id,
                    "paused",
                    "the page changed, so the approved action did not run. hand back when ready.",
                )
                return "stale"
            a.status = "used"  # one use only
            db.commit()
        self._do(live, p["kind"], p["args"])
        self._result(live, p["tool_use_id"], f"Done: {p['kind']} ran after John approved it.")
        live.pending = None
        with self.sf() as db:
            self.step_log(
                db, live.id, "approved", f'you approved "{d.label[:60]}" and it ran once.'
            )
            db.commit()
        self.set_status(live.id, "running")
        return "used"

    # ---------- the step ----------

    def run_until_idle(self, sid: int, max_steps: int | None = None) -> None:
        """Steps while the session is running. The thread runner calls this in the background."""
        n = 0
        while (max_steps is None or n < max_steps) and self.step(sid):
            n += 1

    def step(self, sid: int) -> bool:
        """One model turn. Returns True if the session should keep going."""
        live = self.live.get(sid)
        if live is None:
            return False
        with live.lock:
            with self.sf() as db:
                s = db.get(AgentSession, sid)
                if s.status != "running":
                    return False
                why = self._limit_hit(db, s)
            if why:
                self.set_status(sid, "paused", why, kind="limit")
                return False
            content = live.results + [{"type": "text", "text": n} for n in live.notes]
            if content:
                live.messages.append({"role": "user", "content": content})
                live.results, live.notes = [], []
            try:
                resp = self.llm.next(live.messages)
            except Exception as exc:
                log.warning("agent model call failed: %s", type(exc).__name__)
                self.set_status(sid, "paused", "the model call failed. hand back to retry.")
                return False
            usage = resp.get("usage") or {}
            inp, out = usage.get("input_tokens", 0), usage.get("output_tokens", 0)
            with self.sf() as db:
                db.add(
                    LlmUsage(
                        at=self._now(),
                        purpose=PURPOSE,
                        model=self.st.agent_model,
                        input_tokens=inp,
                        output_tokens=out,
                    )
                )
                s = db.get(AgentSession, sid)
                s.steps, s.input_tokens, s.output_tokens = (
                    s.steps + 1,
                    s.input_tokens + inp,
                    s.output_tokens + out,
                )
                db.commit()
            blocks = resp.get("content") or []
            live.messages.append(
                {"role": "assistant", "content": blocks}
            )  # full content, thinking kept
            stop = resp.get("stop_reason")
            if stop == "refusal":
                self.set_status(sid, "paused", "the model declined this step.")
                return False
            if stop == "max_tokens":
                self.set_status(sid, "paused", "the model's reply was cut off. hand back to retry.")
                return False
            calls = [b for b in blocks if b.get("type") == "tool_use"]
            if not calls:
                self.set_status(
                    sid, "paused", "the agent is waiting for you. send a message or hand back."
                )
                return False
            for i, call in enumerate(calls):
                if not self._handle(live, call):
                    for rest in calls[i + 1 :]:
                        self._result(
                            live, rest["id"], "Not run: an earlier action is waiting for John."
                        )
                    return False
            return True

    def _handle(self, live: Live, call: dict) -> bool:
        """Runs or holds one tool call. False means the session stopped moving."""
        name, args, tid = call.get("name"), call.get("input") or {}, call.get("id")
        if name == "screenshot":
            self._result(live, tid, self._shot(live))
            return True
        if name == "finish":
            self._result(live, tid, "Ended.")
            with self.sf() as db:
                self.step_log(db, live.id, "finish", str(args.get("summary") or "done.")[:300])
                db.commit()
            self.stop(live.id, "finished: " + str(args.get("summary") or "done.")[:250])
            return False
        if name == "ask_john":
            self._result(live, tid, "Asked John. Wait for his reply.")
            self.set_status(
                live.id,
                "paused",
                "agent asks: " + str(args.get("question") or "")[:250],
                kind="ask",
            )
            return False
        if name not in ACTIONS:
            self._result(live, tid, "Unknown tool.", error=True)
            return True
        info = self._inspect(live, name, args)
        d = decide(name, args, info, self.allowed)
        if d.verdict == "run":
            self._do(live, name, args)
            after = self._inspect(live, "page", {})
            self._result(live, tid, "Done.")
            self._log_action(live.id, name, args, d.label, info)
            stop = page_checks(
                after, self.allowed
            )  # where the action landed: sign in, bot check, quiz
            if stop:
                if stop.verdict == "refuse":
                    self.stop(live.id, stop.reason)
                else:
                    self.set_status(live.id, "takeover", stop.reason, kind="gate")
                return False
            return True
        if d.verdict == "block":
            self._result(live, tid, "Blocked: " + d.reason, error=True)
            with self.sf() as db:
                self.step_log(db, live.id, "blocked", d.reason)
                db.commit()
            return True
        if d.verdict == "refuse":
            self._result(live, tid, "Refused: " + d.reason, error=True)
            self.stop(live.id, d.reason)
            return False
        if d.verdict == "pause":
            self._result(live, tid, "Paused: " + d.reason)
            self.set_status(live.id, "takeover", d.reason, kind="gate")
            return False
        # approve: hold the exact action until John decides
        h = action_hash(name, info.get("url") or "", d.label, args)
        with self.sf() as db:
            a = Approval(
                session_id=live.id,
                action_hash=h,
                label=d.label or name,
                status="pending",
                expires_at=self._now() + timedelta(minutes=APPROVAL_MINUTES),
            )
            db.add(a)
            db.commit()
            aid = a.id
        live.pending = {"approval_id": aid, "tool_use_id": tid, "kind": name, "args": args}
        self.set_status(live.id, "needs_approval", d.reason, kind="approval")
        return False

    # ---------- browser helpers ----------

    def _inspect(self, live: Live, kind: str, args: dict) -> dict:
        try:
            if kind == "click":
                return live.driver.inspect(args.get("x"), args.get("y"))
            return live.driver.inspect()
        except Exception:
            return {"url": "", "element": None}  # unknown page: the gate pauses on an empty url

    def _do(self, live: Live, kind: str, args: dict) -> None:
        d = live.driver
        if kind == "click":
            d.click(int(args["x"]), int(args["y"]))
        elif kind == "type_text":
            d.type_text(str(args["text"])[:4000])
        elif kind == "press_key":
            d.press_key([str(k) for k in args.get("keys") or []][:4])
        elif kind == "scroll":
            d.scroll(int(args["x"]), int(args["y"]), int(args["dy"]))
        elif kind == "open_url":
            d.goto(str(args["url"]))

    def _shot(self, live: Live) -> list:
        png = live.driver.screenshot()
        return [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": base64.b64encode(png).decode(),
                },
            }
        ]

    def _result(self, live: Live, tid: str, content, error: bool = False) -> None:
        r = {"type": "tool_result", "tool_use_id": tid, "content": content}
        if error:
            r["is_error"] = True
        live.results.append(r)

    def _log_action(self, sid: int, kind: str, args: dict, label: str, info: dict) -> None:
        from urllib.parse import urlsplit

        host = urlsplit(info.get("url") or "").hostname or "the page"
        line = {
            "click": f'clicked "{label[:60]}" on {host}' if label else f"clicked on {host}",
            "type_text": f"typed {len(str(args.get('text') or ''))} characters",
            "press_key": "pressed " + "+".join(str(k) for k in args.get("keys") or [])[:40],
            "scroll": "scrolled",
            "open_url": f"opened a page on {urlsplit(str(args.get('url'))).hostname}",
        }[kind]
        with self.sf() as db:
            self.step_log(db, sid, kind, line)
            db.commit()
