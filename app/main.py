import logging

from fastapi import FastAPI, Request

from app.api import audit, health
from app.config import Settings
from app.db import make_session_factory
from app.logging_config import new_request_id, setup_logging

log = logging.getLogger("app")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    setup_logging(secrets=[settings.api_token])
    app = FastAPI()
    app.state.settings = settings
    app.state.session_factory = make_session_factory(settings.database_url)
    app.include_router(health.router)
    app.include_router(audit.router)

    @app.middleware("http")
    async def request_id(request: Request, call_next):
        rid = new_request_id()
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        log.info(
            "request_id=%s %s %s %s", rid, request.method, request.url.path, response.status_code
        )
        return response

    return app
