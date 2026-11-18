import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.api import audit, health, sync, today
from app.audit import DbAudit
from app.clock import SystemClock
from app.config import Settings
from app.db import make_session_factory
from app.http_client import GuardedHttpClient
from app.jobs.runner import Runner, default_sources, scheduler_loop
from app.logging_config import new_request_id, setup_logging

log = logging.getLogger("app")


def create_app(settings: Settings | None = None, llm=None, sources=None) -> FastAPI:
    settings = settings or Settings()
    setup_logging(secrets=[settings.api_token])
    stop = threading.Event()

    @asynccontextmanager
    async def lifespan(app):
        if settings.sync_interval_minutes > 0:
            threading.Thread(
                target=scheduler_loop,
                args=(app.state.runner.run_all, settings.sync_interval_minutes * 60, stop),
                daemon=True,
            ).start()
        yield
        stop.set()

    app = FastAPI(lifespan=lifespan)
    app.state.settings = settings
    app.state.llm = llm  # None until a real client is configured: explanations use the template
    app.state.session_factory = make_session_factory(settings.database_url)
    if sources is None:
        http = GuardedHttpClient(DbAudit(app.state.session_factory, SystemClock()))
        sources = default_sources(settings, http)
    app.state.runner = Runner(app.state.session_factory, sources, SystemClock())
    app.include_router(health.router)
    app.include_router(sync.router)
    app.include_router(audit.router)
    app.include_router(today.router)

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
