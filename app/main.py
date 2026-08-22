from __future__ import annotations

import hmac
import logging
from uuid import uuid4

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from app import __version__
from app.config import get_settings
from app.db.session import SessionLocal
from app.observability.health import readiness_snapshot
from app.observability.logging import configure_logging
from app.observability.metrics import collect_metrics, render_prometheus

settings = get_settings()
configure_logging(settings.log_level, settings.log_format)
logger = logging.getLogger(__name__)

app = FastAPI(title="Telegram AI Secretary", version=__version__)


@app.middleware("http")
async def trace_requests(request: Request, call_next):
    trace_id = (request.headers.get("x-trace-id") or uuid4().hex)[:64]
    response = await call_next(request)
    response.headers["x-trace-id"] = trace_id
    logger.info(
        "http_request_complete method=%s path=%s status=%s",
        request.method,
        request.url.path,
        response.status_code,
        extra={"trace_id": trace_id, "operation": "HTTP_REQUEST"},
    )
    return response


@app.get("/health", tags=["system"])
def health() -> dict:
    return {
        "status": "ok",
        "version": __version__,
        "environment": settings.app_env,
    }


@app.get("/ready", tags=["system"])
def ready() -> JSONResponse:
    snapshot = readiness_snapshot(settings)
    return JSONResponse(snapshot.as_dict(), status_code=200 if snapshot.ready else 503)


@app.get("/metrics", tags=["system"], response_class=PlainTextResponse)
def metrics(authorization: str | None = Header(default=None)) -> PlainTextResponse:
    if settings.app_env.lower() == "production" and not settings.metrics_token:
        return PlainTextResponse("Metrics unavailable\n", status_code=503)
    if settings.metrics_token:
        supplied = authorization or ""
        expected = f"Bearer {settings.metrics_token}"
        if not hmac.compare_digest(supplied, expected):
            return PlainTextResponse("Unauthorized\n", status_code=401)
    with SessionLocal() as db:
        snapshot = collect_metrics(db, window_days=settings.metrics_window_days)
    return PlainTextResponse(
        render_prometheus(snapshot),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
