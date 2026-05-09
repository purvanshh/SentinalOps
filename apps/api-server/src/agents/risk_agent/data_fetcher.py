from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from orchestration.state.topology import load_topology
from tools.prometheus.client import PrometheusClient


def _load_historical_incidents(path: str | None = None) -> list[dict[str, Any]]:
    dataset_path = Path(path or "simulation/datasets/historical_incidents.csv")
    if not dataset_path.is_absolute():
        dataset_path = Path.cwd() / dataset_path
    if not dataset_path.exists():
        return []
    with dataset_path.open() as handle:
        return list(csv.DictReader(handle))


async def fetch_live_traffic(service: str, client: PrometheusClient | None = None) -> dict[str, Any]:
    prometheus_client = client or PrometheusClient()
    try:
        payload = await prometheus_client.query_range(
            f"sum(rate(http_requests_total{{service=\"{service}\"}}[5m]))",
            "now-5m",
            "now",
            "60s",
        )
        values: list[float] = []
        for result in payload.get("data", {}).get("result", []):
            for _, value in result.get("values", []):
                try:
                    values.append(float(value))
                except (TypeError, ValueError):
                    continue
        rps = values[-1] if values else 100.0
    except Exception:  # noqa: BLE001
        rps = 100.0
    return {"rps": rps}


async def build_runtime_inputs(service: str) -> dict[str, Any]:
    topology = load_topology()
    traffic = {service: await fetch_live_traffic(service)}
    for node_name in topology:
        if node_name != service:
            traffic.setdefault(node_name, {"rps": 100.0})
    return {
        "topology": topology,
        "traffic": traffic,
        "historical_incidents": _load_historical_incidents(),
    }
