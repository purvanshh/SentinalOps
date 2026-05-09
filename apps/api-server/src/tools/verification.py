from __future__ import annotations

from typing import Any

from tools.prometheus.client import PrometheusClient


async def verify_metric(
    metric_name: str,
    expected_min: float,
    expected_max: float,
    *,
    client: PrometheusClient | None = None,
) -> dict[str, Any]:
    prometheus_client = client or PrometheusClient()
    payload = await prometheus_client.query_range(metric_name, "now-5m", "now", "60s")
    values: list[float] = []
    for result in payload.get("data", {}).get("result", []):
        for _, value in result.get("values", []):
            try:
                values.append(float(value))
            except (TypeError, ValueError):
                continue
    latest_value = values[-1] if values else None
    within_range = latest_value is not None and expected_min <= latest_value <= expected_max
    return {
        "metric_name": metric_name,
        "latest_value": latest_value,
        "expected_min": expected_min,
        "expected_max": expected_max,
        "within_range": within_range,
    }
