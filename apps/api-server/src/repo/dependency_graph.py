from __future__ import annotations

from typing import Any, Dict, List, Set


class DependencyGraph:
    """Builds and analyzes dependency relations of system modules/services."""

    def __init__(self, topology: Any = None) -> None:
        self.dependencies: Dict[str, Set[str]] = {}
        if topology is not None:
            if hasattr(topology, "edges"):
                for u, v in topology.edges:
                    self.add_dependency(u, v)
            elif isinstance(topology, dict):
                for k, v in topology.items():
                    for dep in v:
                        self.add_dependency(k, dep)
        else:
            # Baseline microservice routing dependencies
            self.add_dependency("gateway-service", "payment-api")
            self.add_dependency("gateway-service", "auth-service")
            self.add_dependency("payment-api", "db-service")
            self.add_dependency("payment-api", "notification-service")

    def add_dependency(self, service: str, dependency: str) -> None:
        if service not in self.dependencies:
            self.dependencies[service] = set()
        self.dependencies[service].add(dependency)

    def get_dependencies(self, service: str) -> List[str]:
        return list(self.dependencies.get(service, []))

    def get_dependents(self, service: str) -> List[str]:
        dependents = []
        for k, v in self.dependencies.items():
            if service in v:
                dependents.append(k)
        return dependents
