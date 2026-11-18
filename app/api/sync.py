from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth import require_token

router = APIRouter(dependencies=[Depends(require_token)])


@router.post("/sync/all")
def sync_all(request: Request):
    return request.app.state.runner.run_all()


@router.post("/sync/{source}")
def sync_one(source: str, request: Request):
    if source not in request.app.state.runner.sources:
        raise HTTPException(status_code=404, detail="unknown source")
    return request.app.state.runner.run_sync(source)
