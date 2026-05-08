from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routes.approvals import router as approvals_router
from api.routes.approvals import router as approvals_router
from api.routes.evaluations import router as evaluations_router
from api.routes.graph import router as graph_router
from api.routes.health import router as health_router
from api.routes.incidents import router as incidents_router
from observability.logging import configure_logging
from observability.metrics import build_metrics_snapshot
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
