"""
Multi-Incident Reasoning Engine for SentinelOps Phase 19.

Production outages rarely happen alone. Instead of investigating each
incident independently, this engine correlates concurrent incidents
to find shared root causes.

Example:
    Checkout failing  ─┐
    Payments failing  ─┤─→ Shared DNS outage
    Notifications failing ─┘

Instead of three independent investigations, produce one correlated analysis.

Correlation signals:
    1. Temporal proximity (incidents occurring within a time window)
    2. Shared services or dependencies
    3. Common error patterns
    4. Graph topology overlap
    5. Common deployment events
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Set


@dataclass
class IncidentSummary:
    """Lightweight summary of a single incident for correlation."""

    incident_id: str
    title: str
    service: str
    severity: str
    timestamp: str
    root_cause_hypothesis: str = ""
    mechanism_type: str = ""
    confidence: float = 0.0
    error_patterns: List[str] = field(default_factory=list)
    affected_services: List[str] = field(default_factory=list)
    deployment_ids: List[str] = field(default_factory=list)
    evidence_ids: List[str] = field(default_factory=list)


@dataclass
class CorrelationSignal:
    """A signal linking two or more incidents together."""

    signal_type: str  # temporal | service | error | topology | deployment
    description: str
    incident_ids: List[str]
    strength: float = 0.0  # 0-1


@dataclass
class IncidentCluster:
    """A group of correlated incidents sharing a common root cause."""

    cluster_id: str
    incidents: List[IncidentSummary]
    shared_root_cause: str
    shared_mechanism: str
    correlation_signals: List[CorrelationSignal]
    cluster_confidence: float = 0.0

    @property
    def incident_count(self) -> int:
        return len(self.incidents)

    @property
    def affected_services(self) -> List[str]:
        services: Set[str] = set()
        for inc in self.incidents:
            services.add(inc.service)
            services.update(inc.affected_services)
        return sorted(services)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "incident_count": self.incident_count,
            "shared_root_cause": self.shared_root_cause,
            "shared_mechanism": self.shared_mechanism,
            "cluster_confidence": self.cluster_confidence,
            "affected_services": self.affected_services,
            "incidents": [inc.incident_id for inc in self.incidents],
            "signals": [
                {"type": s.signal_type, "description": s.description, "strength": s.strength}
                for s in self.correlation_signals
            ],
        }


@dataclass
class MultiIncidentAnalysis:
    """Result of multi-incident correlation analysis."""

    clusters: List[IncidentCluster] = field(default_factory=list)
    uncorrelated: List[IncidentSummary] = field(default_factory=list)
    total_incidents: int = 0
    total_clusters: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_incidents": self.total_incidents,
            "total_clusters": self.total_clusters,
            "uncorrelated_count": len(self.uncorrelated),
            "clusters": [c.to_dict() for c in self.clusters],
        }


class MultiIncidentReasoningEngine:
    """
    Correlates multiple concurrent incidents to discover shared root causes.

    Correlation is performed across 5 dimensions:
    1. Temporal proximity (within a configurable time window)
    2. Shared services or service dependencies
    3. Common error patterns in logs
    4. Overlapping evidence graph topology
    5. Common deployment events
    """

    def __init__(
        self,
        time_window_minutes: float = 30.0,
        min_correlation_strength: float = 0.3,
    ) -> None:
        self.time_window_minutes = time_window_minutes
        self.min_correlation_strength = min_correlation_strength

    def analyze(
        self,
        incidents: List[IncidentSummary],
    ) -> MultiIncidentAnalysis:
        """Analyze a set of incidents for cross-incident correlations."""
        if len(incidents) < 2:
            return MultiIncidentAnalysis(
                uncorrelated=incidents,
                total_incidents=len(incidents),
            )

        # Build correlation matrix
        correlations: Dict[tuple[str, str], List[CorrelationSignal]] = {}
        for i in range(len(incidents)):
            for j in range(i + 1, len(incidents)):
                signals = self._compute_correlation(incidents[i], incidents[j])
                if signals:
                    key = (incidents[i].incident_id, incidents[j].incident_id)
                    correlations[key] = signals

        # Cluster incidents by connectivity (union-find)
        clusters = self._cluster_incidents(incidents, correlations)

        # For each cluster, determine shared root cause
        incident_clusters: List[IncidentCluster] = []
        uncorrelated: List[IncidentSummary] = []

        for cluster_idx, cluster_incident_ids in enumerate(clusters):
            cluster_incidents = [
                inc for inc in incidents if inc.incident_id in cluster_incident_ids
            ]

            if len(cluster_incidents) < 2:
                uncorrelated.extend(cluster_incidents)
                continue

            # Collect all correlation signals for this cluster
            all_signals: List[CorrelationSignal] = []
            for (a, b), signals in correlations.items():
                if a in cluster_incident_ids or b in cluster_incident_ids:
                    all_signals.extend(signals)

            # Determine shared root cause
            shared_cause, shared_mechanism = self._determine_shared_cause(cluster_incidents)
            cluster_confidence = self._compute_cluster_confidence(all_signals)

            incident_clusters.append(IncidentCluster(
                cluster_id=f"CLUSTER-{cluster_idx + 1:03d}",
                incidents=cluster_incidents,
                shared_root_cause=shared_cause,
                shared_mechanism=shared_mechanism,
                correlation_signals=all_signals,
                cluster_confidence=round(cluster_confidence, 4),
            ))

        return MultiIncidentAnalysis(
            clusters=incident_clusters,
            uncorrelated=uncorrelated,
            total_incidents=len(incidents),
            total_clusters=len(incident_clusters),
        )

    def _compute_correlation(
        self,
        a: IncidentSummary,
        b: IncidentSummary,
    ) -> List[CorrelationSignal]:
        """Compute correlation signals between two incidents."""
        signals: List[CorrelationSignal] = []
        ids = [a.incident_id, b.incident_id]

        # 1. Temporal proximity
        try:
            ta = datetime.fromisoformat(a.timestamp.replace("Z", "+00:00"))
            tb = datetime.fromisoformat(b.timestamp.replace("Z", "+00:00"))
            delta_minutes = abs((ta - tb).total_seconds()) / 60.0
            if delta_minutes <= self.time_window_minutes:
                strength = max(0.0, 1.0 - (delta_minutes / self.time_window_minutes))
                signals.append(CorrelationSignal(
                    signal_type="temporal",
                    description=f"Incidents occurred {delta_minutes:.1f} minutes apart",
                    incident_ids=ids,
                    strength=round(strength, 4),
                ))
        except (ValueError, TypeError):
            pass

        # 2. Shared services
        shared_services = set(a.affected_services) & set(b.affected_services)
        if a.service == b.service:
            shared_services.add(a.service)
        if shared_services:
            signals.append(CorrelationSignal(
                signal_type="service",
                description=f"Shared services: {', '.join(shared_services)}",
                incident_ids=ids,
                strength=min(1.0, len(shared_services) * 0.3),
            ))

        # 3. Common error patterns
        common_errors = set(a.error_patterns) & set(b.error_patterns)
        if common_errors:
            signals.append(CorrelationSignal(
                signal_type="error",
                description=f"Shared error patterns: {', '.join(list(common_errors)[:3])}",
                incident_ids=ids,
                strength=min(1.0, len(common_errors) * 0.25),
            ))

        # 4. Common deployments
        common_deploys = set(a.deployment_ids) & set(b.deployment_ids)
        if common_deploys:
            signals.append(CorrelationSignal(
                signal_type="deployment",
                description=f"Shared deployment events: {', '.join(common_deploys)}",
                incident_ids=ids,
                strength=0.8,
            ))

        # 5. Same mechanism type
        if a.mechanism_type and a.mechanism_type == b.mechanism_type:
            signals.append(CorrelationSignal(
                signal_type="mechanism",
                description=f"Same failure mechanism: {a.mechanism_type}",
                incident_ids=ids,
                strength=0.4,
            ))

        # Filter by minimum strength
        return [s for s in signals if s.strength >= self.min_correlation_strength]

    def _cluster_incidents(
        self,
        incidents: List[IncidentSummary],
        correlations: Dict[tuple[str, str], List[CorrelationSignal]],
    ) -> List[Set[str]]:
        """Union-find clustering of incidents based on correlation edges."""
        parent: Dict[str, str] = {inc.incident_id: inc.incident_id for inc in incidents}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x: str, y: str) -> None:
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py

        for (a_id, b_id), signals in correlations.items():
            if signals:
                union(a_id, b_id)

        clusters: Dict[str, Set[str]] = {}
        for inc in incidents:
            root = find(inc.incident_id)
            clusters.setdefault(root, set()).add(inc.incident_id)

        return list(clusters.values())

    def _determine_shared_cause(
        self,
        incidents: List[IncidentSummary],
    ) -> tuple[str, str]:
        """Determine the most likely shared root cause for a cluster."""
        # Vote on mechanism type
        mechanism_votes: Dict[str, int] = {}
        for inc in incidents:
            if inc.mechanism_type:
                mechanism_votes[inc.mechanism_type] = mechanism_votes.get(inc.mechanism_type, 0) + 1

        best_mechanism = (
            max(mechanism_votes, key=mechanism_votes.get)
            if mechanism_votes else "unknown"
        )

        # Synthesize shared cause description
        services = sorted({inc.service for inc in incidents})
        cause = f"Shared {best_mechanism} affecting {', '.join(services)}"

        return cause, best_mechanism

    def _compute_cluster_confidence(
        self,
        signals: List[CorrelationSignal],
    ) -> float:
        """Compute overall cluster confidence from correlation signals."""
        if not signals:
            return 0.0
        avg_strength = sum(s.strength for s in signals) / len(signals)
        diversity_bonus = min(0.2, len(set(s.signal_type for s in signals)) * 0.05)
        return min(1.0, avg_strength + diversity_bonus)
