from fastapi import FastAPI

app = FastAPI(title="notification-service-mock")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "notification-service"}


@app.get("/metrics")
async def metrics() -> str:
    return """
# HELP notification_queue_depth Notification queue depth
# TYPE notification_queue_depth gauge
notification_queue_depth 128
# HELP notification_delivery_latency Notification delivery latency
# TYPE notification_delivery_latency gauge
notification_delivery_latency 0.34
""".strip()


@app.get("/logs")
async def logs() -> dict[str, list[str]]:
    return {
        "entries": [
            "2026-05-11T09:05:00Z Notification dispatch delayed by downstream rate limit trace=notify-001",
            "2026-05-11T09:05:03Z Queue backlog crossed warning threshold trace=notify-002",
        ]
    }
