from fastapi import FastAPI

app = FastAPI(title="payment-service-mock")


@app.get("/metrics")
async def metrics() -> str:
    return """
# HELP payment_api_cpu CPU utilization
# TYPE payment_api_cpu gauge
payment_api_cpu 0.98
# HELP payment_api_latency_p99 Latency p99
# TYPE payment_api_latency_p99 gauge
payment_api_latency_p99 0.9
""".strip()


@app.get("/logs")
async def logs() -> dict[str, list[str]]:
    return {
        "entries": [
            "2026-05-08T14:03:01Z TimeoutException in payment flow trace=abc123",
            "2026-05-08T14:03:04Z TimeoutException in payment flow trace=def456",
        ]
    }
