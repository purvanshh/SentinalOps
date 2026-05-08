from pathlib import Path

import yaml

from core.config import get_settings
from orchestration.state.topology_schema import ServiceNode


def load_topology(path: str | None = None) -> dict[str, ServiceNode]:
    settings = get_settings()
    topology_path = Path(path or settings.topology_path)
    if not topology_path.is_absolute():
        topology_path = Path.cwd() / topology_path

    if not topology_path.exists():
        return {}

    raw = yaml.safe_load(topology_path.read_text()) or {}
    services = raw.get("services", [])
    return {item["name"]: ServiceNode.model_validate(item) for item in services}


def get_dependencies(service: str, topology: dict[str, ServiceNode] | None = None) -> list[ServiceNode]:
    graph = topology or load_topology()
    node = graph.get(service)
    if node is None:
        return []
    return [graph[name] for name in node.depends_on if name in graph]
