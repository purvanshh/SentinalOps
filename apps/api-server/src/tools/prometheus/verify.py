from __future__ import annotations

from typing import Any

from tools.prometheus.client import PrometheusClient


async def verify_metric(
    metric: str,
    expected_range: tuple[float, float],
    *,
    client: PrometheusClient | None = None,
) -> dict[str, Any]:
    prometheus_client = client or PrometheusClient()
    payload = await prometheus_client.query_range(metric, "now-5m", "now", "60s")
    values: list[float] = []
    for result in payload.get("data", {}).get("result", []):
        for _, value in result.get("values", []):
            try:
                values.append(float(value))
            except (TypeError, ValueError):
                continue
    latest_value = values[-1] if values else None
    min_expected, max_expected = expected_range
    within_range = latest_value is not None and min_expected <= latest_value <= max_expected
    return {
        "metric_name": metric,
        "latest_value": latest_value,
        "expected_range": {
            "min": min_expected,
            "max": max_expected,
        },
        "within_range": within_range,
    }
