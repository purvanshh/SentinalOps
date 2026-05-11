from fastapi import FastAPI

app = FastAPI(title="gateway-service-mock")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "gateway-service"}


@app.get("/metrics")
async def metrics() -> str:
    return """
# HELP gateway_requests_per_second Request throughput
# TYPE gateway_requests_per_second gauge
gateway_requests_per_second 842
# HELP gateway_error_rate Gateway error rate
# TYPE gateway_error_rate gauge
gateway_error_rate 0.12
""".strip()


@app.get("/logs")
async def logs() -> dict[str, list[str]]:
    return {
        "entries": [
            "2026-05-11T09:10:00Z Upstream payment-api returned 504 trace=gateway-001",
            "2026-05-11T09:10:02Z Circuit breaker opened for payment-api trace=gateway-002",
        ]
    }
