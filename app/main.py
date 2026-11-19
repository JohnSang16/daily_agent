import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.api import ask, audit, banks, digest, health, local, money, sync, today
from app.audit import DbAudit
from app.clock import SystemClock
from app.config import Settings
from app.db import make_session_factory
from app.http_client import GuardedHttpClient
from app.jobs.runner import Runner, banks_source, default_sources, scheduler_loop
from app.llm.anthropic_client import AnthropicClient
from app.logging_config import new_request_id, setup_logging
from app.sources.plaid import PlaidClient

log = logging.getLogger("app")


def create_app(settings: Settings | None = None, llm=None, sources=None, plaid=None) -> FastAPI:
    settings = settings or Settings()
    setup_logging(
        secrets=[
            settings.api_token,
            settings.anthropic_api_key,
            settings.plaid_secret,
            settings.token_encryption_key,
        ]
    )
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
    app.state.session_factory = make_session_factory(settings.database_url)
    http = GuardedHttpClient(DbAudit(app.state.session_factory, SystemClock()))
    if llm is None and settings.anthropic_api_key and settings.llm_model:
        llm = AnthropicClient(http, settings.anthropic_api_key, settings.llm_model)
    app.state.llm = llm  # None: explanations use the template
    if plaid is None and settings.plaid_client_id and settings.plaid_secret:
        plaid = PlaidClient(http, settings)
    app.state.plaid = plaid
    if sources is None:
        sources = default_sources(settings, http, plaid)
    elif plaid is not None and "banks" not in sources:
        sources = {**sources, "banks": banks_source(settings, plaid)}
    app.state.runner = Runner(app.state.session_factory, sources, SystemClock())
    app.include_router(health.router)
    app.include_router(sync.router)
    app.include_router(local.router)
    app.include_router(ask.router)
    app.include_router(digest.router)
    app.include_router(banks.router)
    app.include_router(money.router)
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
