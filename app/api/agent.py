"""Spec 13 endpoints. All need the bearer token. The live view URL is returned only while the
session is active and is never logged."""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.ask import split_course
from app.auth import require_token
from app.models import AgentSession, AgentStep, Approval, Task

log = logging.getLogger("agent")
router = APIRouter(dependencies=[Depends(require_token)])
START = {
    "icollege": "https://gastate.view.usg.edu/d2l/home",
    "pearson": "https://mylab.pearson.com/",
}
ACTIVE = {"starting", "running", "paused", "takeover", "needs_approval"}


def _agent(request: Request):
    a = getattr(request.app.state, "agent", None)
    if a is None:
        raise HTTPException(
            503, "the homework agent is not configured (KERNEL_API_KEY and ANTHROPIC_API_KEY)"
        )
    return a


def _kick(request: Request, sid: int) -> None:
    request.app.state.agent_runner(sid)


class StartIn(BaseModel):
    task_id: int
    site: Literal["icollege", "pearson"] = "icollege"


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class DecisionIn(BaseModel):
    decision: Literal["approve", "deny"]


def _view(request: Request, sid: int) -> dict:
    agent = getattr(request.app.state, "agent", None)
    with request.app.state.session_factory() as db:
        s = db.get(AgentSession, sid)
        if s is None:
            raise HTTPException(404, "not found")
        live = agent.live.get(sid) if agent else None
        if s.status in ACTIVE and live is None:  # the agent restarted and lost the browser
            s.status, s.reason = "ended", "the agent restarted, so this session ended."
            db.commit()
        steps = db.scalars(
            select(AgentStep)
            .where(AgentStep.session_id == sid)
            .order_by(AgentStep.id.desc())
            .limit(60)
        ).all()
        pending = db.scalars(
            select(Approval).where(Approval.session_id == sid, Approval.status == "pending")
        ).first()
        return {
            "id": s.id,
            "title": s.title,
            "site": s.site,
            "status": s.status,
            "reason": s.reason,
            "steps": [
                {"at": x.at.isoformat(), "kind": x.kind, "summary": x.summary}
                for x in reversed(steps)
            ],
            "approval": {
                "id": pending.id,
                "label": pending.label,
                "expires_at": pending.expires_at.isoformat(),
            }
            if pending
            else None,
            "live_view_url": live.live_view_url if live and s.status in ACTIVE else None,
            "usage": {
                "steps": s.steps,
                "input_tokens": s.input_tokens,
                "output_tokens": s.output_tokens,
            },
        }


@router.post("/agent/sessions")
def start(body: StartIn, request: Request):
    agent = _agent(request)
    with request.app.state.session_factory() as db:
        t = db.get(Task, body.task_id)
        if t is None or t.status != "open":
            raise HTTPException(404, "task not found")
        title, _ = split_course(t.title)
    if any(True for _ in agent.live):
        raise HTTPException(409, "a homework session is already running. stop it first.")
    try:
        sid = agent.start(body.task_id, title, body.site, START[body.site])
    except Exception as exc:
        log.warning("session start failed: %s", type(exc).__name__)
        raise HTTPException(502, "the browser could not start") from None
    _kick(request, sid)
    return _view(request, sid)


@router.get("/agent/sessions/{sid}")
def get_session(sid: int, request: Request):
    return _view(request, sid)


@router.post("/agent/sessions/{sid}/message")
def message(sid: int, body: MessageIn, request: Request):
    _agent(request).message(sid, body.text)
    return _view(request, sid)


@router.post("/agent/sessions/{sid}/{action}")
def control(sid: int, action: Literal["pause", "takeover", "handback", "stop"], request: Request):
    agent = _agent(request)
    _view(request, sid)  # 404 for an unknown session
    if action == "stop":
        agent.stop(sid)
    elif action == "pause":
        agent.pause(sid)
    elif action == "takeover":
        agent.pause(sid, "takeover", "you have control in the live view. hand back when done.")
    else:
        agent.handback(sid)
        _kick(request, sid)
    return _view(request, sid)


@router.post("/agent/sessions/{sid}/approvals/{aid}")
def approval(sid: int, aid: int, body: DecisionIn, request: Request):
    agent = _agent(request)
    result = agent.decide_approval(sid, aid, body.decision == "approve")
    if result == "not_found":
        raise HTTPException(404, "not found")
    if result == "expired":
        raise HTTPException(410, "that approval expired. hand back and let the agent ask again.")
    if result == "used":
        _kick(request, sid)
    return {**_view(request, sid), "result": result}
