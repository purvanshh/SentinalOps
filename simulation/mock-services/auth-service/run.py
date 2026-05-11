from fastapi import FastAPI

app = FastAPI(title="auth-service-mock")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "auth-service"}


@app.get("/metrics")
async def metrics() -> str:
    return """
# HELP auth_service_error_rate Authentication error rate
# TYPE auth_service_error_rate gauge
auth_service_error_rate 0.04
# HELP auth_service_latency_p95 Authentication latency p95
# TYPE auth_service_latency_p95 gauge
auth_service_latency_p95 0.18
""".strip()


@app.get("/logs")
async def logs() -> dict[str, list[str]]:
    return {
        "entries": [
            "2026-05-11T09:00:00Z Auth token validation retried trace=auth-001",
            "2026-05-11T09:00:05Z Upstream identity provider timeout trace=auth-002",
        ]
    }
