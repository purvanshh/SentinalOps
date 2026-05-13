"""
Causal hallucination detection for SentinelOps Phase 43.

Detects when the causal reasoning engine makes claims that violate:
  1. Topology constraints — propagation through non-existent dependencies
  2. Temporal constraints — cause occurring after effect
  3. Reverse causality — effect being labeled as the cause
  4. Deployment timing — deployment blamed when it post-dated the incident
  5. Impossible propagation — alert storm unrelated to causal chain

Each violation is a CausalHallucination with:
  - violation_type: what kind of constraint was violated
  - claimed_cause: the candidate being falsely attributed
  - claimed_effect: what it was claimed to cause
  - evidence: why this is a hallucination
  - severity: "critical" (fundamentally wrong) or "warning" (suspicious)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from causality.temporal_engine import _elapsed_seconds


class HallucinationType(str, Enum):
    TOPOLOGY_VIOLATION = "topology_violation"
    TEMPORAL_CONTRADICTION = "temporal_contradiction"
    REVERSE_CAUSALITY = "reverse_causality"
    DEPLOYMENT_AFTER_INCIDENT = "deployment_after_incident"
    IMPOSSIBLE_PROPAGATION = "impossible_propagation"
    ALERT_STORM_MISATTRIBUTION = "alert_storm_misattribution"


@dataclass
class CausalHallucination:
    """A detected hallucination in causal attribution."""

    violation_type: HallucinationType
    claimed_cause_id: str
    claimed_effect_id: str
    evidence: str
    severity: str = "critical"


@dataclass
class HallucinationReport:
    """Aggregated results of hallucination detection."""

    violations: list[CausalHallucination] = field(default_factory=list)
    suppressed_candidates: list[str] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        """True when no critical hallucinations found."""
        return not any(h.severity == "critical" for h in self.violations)

    @property
    def critical_count(self) -> int:
        return sum(1 for h in self.violations if h.severity == "critical")

    @property
    def warning_count(self) -> int:
        return sum(1 for h in self.violations if h.severity == "warning")


def detect_topology_violations(
    causal_claims: list[dict[str, Any]],
    topology: dict[str, Any],
) -> list[CausalHallucination]:
    """
    Detect claims where the cause_service has no topology path to effect_service.

    causal_claims: list of dicts with keys: cause_id, cause_service,
                   effect_id, effect_service.
    """
    deps = topology.get("dependencies", {})
    violations: list[CausalHallucination] = []

    def has_path(src: str, dst: str) -> bool:
        if src == dst:
            return True
        visited: set[str] = set()
        queue = [src]
        while queue:
            current = queue.pop(0)
            for neighbor in deps.get(current, []):
                if neighbor == dst:
                    return True
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        return False

    for claim in causal_claims:
        cause_svc = claim.get("cause_service", "")
        effect_svc = claim.get("effect_service", "")
        if not cause_svc or not effect_svc or not topology:
            continue
        if not has_path(cause_svc, effect_svc):
            violations.append(
                CausalHallucination(
                    violation_type=HallucinationType.TOPOLOGY_VIOLATION,
                    claimed_cause_id=claim.get("cause_id", ""),
                    claimed_effect_id=claim.get("effect_id", ""),
                    evidence=(
                        f"no dependency path from '{cause_svc}' to '{effect_svc}' "
                        "in the service topology — propagation is impossible"
                    ),
                    severity="critical",
                )
            )
    return violations


def detect_temporal_contradictions(
    causal_claims: list[dict[str, Any]],
) -> list[CausalHallucination]:
    """
    Detect claims where cause_timestamp is AFTER effect_timestamp.

    causal_claims: list of dicts with keys: cause_id, cause_timestamp_iso,
                   effect_id, effect_timestamp_iso.
    """
    violations: list[CausalHallucination] = []
    for claim in causal_claims:
        cause_ts = claim.get("cause_timestamp_iso", "")
        effect_ts = claim.get("effect_timestamp_iso", "")
        if not cause_ts or not effect_ts:
            continue
        elapsed = _elapsed_seconds(cause_ts, effect_ts)
        if elapsed < 0:
            violations.append(
                CausalHallucination(
                    violation_type=HallucinationType.TEMPORAL_CONTRADICTION,
                    claimed_cause_id=claim.get("cause_id", ""),
                    claimed_effect_id=claim.get("effect_id", ""),
                    evidence=(
                        f"claimed cause at {cause_ts} occurred "
                        f"{abs(elapsed):.0f}s AFTER the effect at {effect_ts}"
                    ),
                    severity="critical",
                )
            )
    return violations


def detect_deployment_misattribution(
    deployment_events: list[dict[str, Any]],
    incident_onset_timestamp: str,
) -> list[CausalHallucination]:
    """
    Flag deployments that occurred after the incident started as false causes.

    deployment_events: list of dicts with keys: id, timestamp_iso, service.
    incident_onset_timestamp: ISO timestamp of first detected anomaly.
    """
    violations: list[CausalHallucination] = []
    for deploy in deployment_events:
        deploy_ts = deploy.get("timestamp_iso", "")
        if not deploy_ts:
            continue
        elapsed = _elapsed_seconds(incident_onset_timestamp, deploy_ts)
        if elapsed > 0:
            violations.append(
                CausalHallucination(
                    violation_type=HallucinationType.DEPLOYMENT_AFTER_INCIDENT,
                    claimed_cause_id=deploy.get("id", "deployment"),
                    claimed_effect_id="incident",
                    evidence=(
                        f"deployment at {deploy_ts} occurred {elapsed:.0f}s "
                        f"after incident onset at {incident_onset_timestamp} "
                        "— cannot be the root cause"
                    ),
                    severity="critical",
                )
            )
    return violations


def detect_alert_storm_misattribution(
    alerts: list[dict[str, Any]],
    causal_service: str,
    topology: dict[str, Any],
) -> list[CausalHallucination]:
    """
    Flag alerts attributed to causal_service that have no topology connection.

    alerts: list of dicts with keys: id, service, attributed_to (service name).
    """
    deps = topology.get("dependencies", {})
    violations: list[CausalHallucination] = []

    def connected(a: str, b: str) -> bool:
        for src, targets in deps.items():
            if (src == a and b in targets) or (src == b and a in targets):
                return True
        return a == b

    for alert in alerts:
        attributed_to = alert.get("attributed_to", "")
        alert_service = alert.get("service", "")
        if not attributed_to or not alert_service or not topology:
            continue
        if attributed_to == causal_service and not connected(alert_service, causal_service):
            violations.append(
                CausalHallucination(
                    violation_type=HallucinationType.ALERT_STORM_MISATTRIBUTION,
                    claimed_cause_id=causal_service,
                    claimed_effect_id=alert.get("id", "alert"),
                    evidence=(
                        f"alert from '{alert_service}' attributed to '{causal_service}' "
                        "but no topology connection exists — likely collateral noise"
                    ),
                    severity="warning",
                )
            )
    return violations


def run_hallucination_detection(
    causal_claims: list[dict[str, Any]],
    *,
    topology: dict[str, Any] | None = None,
    deployment_events: list[dict[str, Any]] | None = None,
    incident_onset_timestamp: str = "",
    alert_storm_alerts: list[dict[str, Any]] | None = None,
    causal_service: str = "",
) -> HallucinationReport:
    """Full hallucination detection pass over all claim types."""
    report = HallucinationReport()

    if topology:
        report.violations.extend(detect_topology_violations(causal_claims, topology))

    report.violations.extend(detect_temporal_contradictions(causal_claims))

    if deployment_events and incident_onset_timestamp:
        report.violations.extend(
            detect_deployment_misattribution(deployment_events, incident_onset_timestamp)
        )

    if alert_storm_alerts and causal_service and topology:
        report.violations.extend(
            detect_alert_storm_misattribution(alert_storm_alerts, causal_service, topology)
        )

    # Suppress critical violating candidates
    for v in report.violations:
        if v.severity == "critical" and v.claimed_cause_id not in report.suppressed_candidates:
            report.suppressed_candidates.append(v.claimed_cause_id)

    return report
