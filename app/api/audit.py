from fastapi import APIRouter, Depends, Request

from app.audit import summarize
from app.auth import require_token
from app.clock import Clock, get_clock

router = APIRouter(dependencies=[Depends(require_token)])


@router.get("/audit/outbound")
def outbound(request: Request, clock: Clock = Depends(get_clock)):
    return summarize(request.app.state.session_factory, clock)
