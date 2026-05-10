from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, Response

from api.middleware.auth import AuthMiddleware
from api.middleware.error_handler import (
    http_exception_handler,
    permission_exception_handler,
    unhandled_exception_handler,
)
from api.routes.approvals import router as approvals_router
from api.routes.evaluations import router as evaluations_router
from api.routes.graph import router as graph_router
from api.routes.health import router as health_router
from api.routes.incidents import router as incidents_router
from api.ws.incident_stream import router as incident_stream_router
from observability.logging import bind_request_id, configure_logging
from observability.metrics import build_metrics_snapshot, observe_api_request, render_metrics
from observability.tracing import configure_tracing


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    configure_tracing()
    yield


app = FastAPI(
    title="SentinelOps AI API",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(AuthMiddleware)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(PermissionError, permission_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid4()))
    bind_request_id(request_id)
    observe_api_request(request.method, request.url.path)
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response

app.include_router(health_router)
app.include_router(incidents_router)
app.include_router(approvals_router)
app.include_router(graph_router)
app.include_router(evaluations_router)
app.include_router(incident_stream_router)


@app.get("/", tags=["root"])
async def root() -> dict[str, object]:
    return {
        "name": "SentinelOps AI",
        "status": "ok",
        "metrics": build_metrics_snapshot(),
    }


@app.get("/metrics", tags=["observability"])
async def metrics() -> Response:
    payload, content_type = render_metrics()
    return Response(content=payload, media_type=content_type)
