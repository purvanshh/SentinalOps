from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request, Response

from api.middleware.auth import AuthMiddleware
from api.routes.approvals import router as approvals_router
from api.routes.evaluations import router as evaluations_router
from api.routes.graph import router as graph_router
from api.routes.health import router as health_router
from api.routes.incidents import router as incidents_router
from observability.logging import bind_request_id, configure_logging
from observability.metrics import API_REQUEST_COUNT, build_metrics_snapshot, render_metrics
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


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid4()))
    bind_request_id(request_id)
    API_REQUEST_COUNT.inc()
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response

app.include_router(health_router)
app.include_router(incidents_router)
app.include_router(approvals_router)
app.include_router(graph_router)
app.include_router(evaluations_router)


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
