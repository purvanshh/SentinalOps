from collections import deque
from datetime import datetime

from orchestration.state.topology_schema import ServiceNode


def is_valid_path(
    cause_service: str,
    effect_service: str,
    topology_graph: dict[str, ServiceNode],
) -> bool:
    if cause_service == effect_service:
        return True

    reverse_graph: dict[str, list[str]] = {}
    for service_name, node in topology_graph.items():
        for dependency in node.depends_on:
            reverse_graph.setdefault(dependency, []).append(service_name)

    queue: deque[str] = deque([cause_service])
    seen = {cause_service}
    while queue:
        current = queue.popleft()
        for downstream in reverse_graph.get(current, []):
            if downstream == effect_service:
                return True
            if downstream not in seen:
                seen.add(downstream)
                queue.append(downstream)
    return False


def check_temporal_order(evidence_items: list[dict]) -> bool:
    timestamps: list[datetime] = []
    for item in evidence_items:
        raw = item.get("timestamp")
        if not raw:
            continue
        try:
            timestamps.append(datetime.fromisoformat(raw.replace("Z", "+00:00")))
        except ValueError:
            continue
    return timestamps == sorted(timestamps)
