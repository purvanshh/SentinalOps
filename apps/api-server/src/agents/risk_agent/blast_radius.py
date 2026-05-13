import json
import random
from pathlib import Path

from orchestration.state.topology_schema import ServiceNode


def _downstream_services(service: str, topology: dict[str, ServiceNode]) -> list[str]:
    reverse_graph: dict[str, list[str]] = {}
    for name, node in topology.items():
        for dependency in node.depends_on:
            reverse_graph.setdefault(dependency, []).append(name)
    seen = {service}
    queue = [service]
    impacted: list[str] = [service]
    while queue:
        current = queue.pop(0)
        for downstream in reverse_graph.get(current, []):
            if downstream not in seen:
                seen.add(downstream)
                impacted.append(downstream)
                queue.append(downstream)
    return impacted


def load_traffic_snapshots(path: str | None = None) -> dict:
    snapshot_path = Path(path or "simulation/datasets/traffic_snapshots.json")
    if not snapshot_path.is_absolute():
        snapshot_path = Path.cwd() / snapshot_path
    if not snapshot_path.exists():
        return {}
    return json.loads(snapshot_path.read_text())


def compute_blast_radius(
    affected_service: str,
    topology: dict[str, ServiceNode],
    traffic_data: dict | None = None,
    severity_factor: float = 0.2,
    samples: int = 1000,
) -> dict:
    traffic = traffic_data or load_traffic_snapshots()
    impacted_services = _downstream_services(affected_service, topology)
    estimates: list[int] = []
    rng = random.Random(42)
    for _ in range(samples):
        total_requests = 0.0
        for service in impacted_services:
            base_rps = float(traffic.get(service, {}).get("rps", 100))
            multiplier = rng.uniform(max(0.05, severity_factor - 0.05), severity_factor + 0.05)
            total_requests += base_rps * multiplier
        estimates.append(int(total_requests * 10))
    estimates.sort()
    mean = int(sum(estimates) / len(estimates))
    p90 = estimates[int(0.9 * (len(estimates) - 1))]
    return {
        "affected_services": impacted_services,
        "users_at_risk": {
            "mean": mean,
            "p90": p90,
            "description": (
                f"If {affected_service} remains degraded, downstream services "
                f"may impact about {mean} users."
            ),
        },
    }
