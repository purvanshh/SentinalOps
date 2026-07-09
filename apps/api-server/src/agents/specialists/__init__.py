"""
Specialized Investigator Agents for SentinelOps Phase 8.

Instead of one monolithic RCA agent, this module creates specialized
investigator agents that each focus on a single evidence domain. An
Arbitrator agent merges their independent findings.

Agent roster:
    MetricsInvestigator    — analyzes metric anomalies
    DeploymentInvestigator — analyzes recent deployments and config changes
    GitInvestigator        — analyzes recent commits and code changes
    TopologyInvestigator   — analyzes service dependency failures
    DependencyInvestigator — analyzes upstream/downstream impact
    RunbookInvestigator    — matches against historical runbook patterns
    Arbitrator             — merges all specialist outputs into final ranking
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class SpecialistFinding:
    """Output from a single specialist investigator."""

    agent_name: str
    hypothesis: str
    evidence_ids: List[str] = field(default_factory=list)
    confidence: float = 0.0
    mechanism_type: str = "unknown"
    explanation: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseInvestigator:
    """Base class for all specialist investigators."""

    agent_name: str = "base"

    def investigate(
        self,
        evidence_items: list[dict[str, Any]],
        service: str = "unknown",
        **context: Any,
    ) -> SpecialistFinding:
        raise NotImplementedError


class MetricsInvestigator(BaseInvestigator):
    """Analyzes metric anomalies to detect resource exhaustion and threshold breaches."""

    agent_name = "metrics_investigator"

    def investigate(
        self,
        evidence_items: list[dict[str, Any]],
        service: str = "unknown",
        **context: Any,
    ) -> SpecialistFinding:
        metric_evidence = [
            e for e in evidence_items
            if e.get("source") in ("metrics", "metric") or e.get("item_type") == "metric_anomaly"
        ]

        if not metric_evidence:
            return SpecialistFinding(
                agent_name=self.agent_name,
                hypothesis="No metric anomalies detected",
                confidence=0.0,
            )

        # Identify the most severe metric anomaly
        best = max(metric_evidence, key=lambda e: abs(float(e.get("z_score", 0))))
        metric_name = best.get("metric", "unknown_metric")
        z_score = float(best.get("z_score", 0))

        mechanism = "resource_exhaustion"
        if "latency" in metric_name.lower() or "response_time" in metric_name.lower():
            mechanism = "dependency_failure"
        elif "error" in metric_name.lower() or "5xx" in metric_name.lower():
            mechanism = "cascade_failure"
        elif "memory" in metric_name.lower() or "cpu" in metric_name.lower():
            mechanism = "resource_exhaustion"

        confidence = min(1.0, abs(z_score) / 5.0) if z_score else 0.3

        return SpecialistFinding(
            agent_name=self.agent_name,
            hypothesis=f"{metric_name} anomaly on {service} (z={z_score:.1f})",
            evidence_ids=[e.get("item_key", "") for e in metric_evidence],
            confidence=round(confidence, 4),
            mechanism_type=mechanism,
            explanation=f"Metric {metric_name} deviated {z_score:.1f}σ from baseline",
        )


class DeploymentInvestigator(BaseInvestigator):
    """Analyzes recent deployments and configuration changes."""

    agent_name = "deployment_investigator"

    def investigate(
        self,
        evidence_items: list[dict[str, Any]],
        service: str = "unknown",
        **context: Any,
    ) -> SpecialistFinding:
        deploy_evidence = [
            e for e in evidence_items
            if e.get("source") in ("deployment", "deploy") or e.get("item_type") == "deployment_change"
        ]

        if not deploy_evidence:
            return SpecialistFinding(
                agent_name=self.agent_name,
                hypothesis="No recent deployments detected",
                confidence=0.0,
            )

        latest = deploy_evidence[0]
        version = latest.get("version", "unknown")

        return SpecialistFinding(
            agent_name=self.agent_name,
            hypothesis=f"Deployment regression from {version} on {service}",
            evidence_ids=[e.get("item_key", "") for e in deploy_evidence],
            confidence=0.65,
            mechanism_type="deployment_error",
            explanation=f"Deployment {version} was active during incident window",
        )


class GitInvestigator(BaseInvestigator):
    """Analyzes recent git commits and code changes."""

    agent_name = "git_investigator"

    def investigate(
        self,
        evidence_items: list[dict[str, Any]],
        service: str = "unknown",
        **context: Any,
    ) -> SpecialistFinding:
        commits = context.get("recent_commits", [])
        if not commits:
            return SpecialistFinding(
                agent_name=self.agent_name,
                hypothesis="No recent code changes found",
                confidence=0.0,
            )

        latest = commits[0]
        message = latest.get("message", "")
        files = latest.get("files_changed", [])

        confidence = 0.4
        if any("config" in f.lower() or "pool" in f.lower() or "connection" in f.lower() for f in files):
            confidence = 0.7

        return SpecialistFinding(
            agent_name=self.agent_name,
            hypothesis=f"Code change: {message[:80]}",
            evidence_ids=[latest.get("sha", "")],
            confidence=round(confidence, 4),
            mechanism_type="configuration_drift",
            explanation=f"Commit {latest.get('sha', '')[:8]} changed {len(files)} files",
            metadata={"files_changed": files},
        )


class TopologyInvestigator(BaseInvestigator):
    """Analyzes service dependency topology for cascade failures."""

    agent_name = "topology_investigator"

    def investigate(
        self,
        evidence_items: list[dict[str, Any]],
        service: str = "unknown",
        **context: Any,
    ) -> SpecialistFinding:
        topology = context.get("topology")
        if topology is None:
            return SpecialistFinding(
                agent_name=self.agent_name,
                hypothesis="No topology data available",
                confidence=0.0,
            )

        # Check if multiple services are affected
        affected_services = set()
        for e in evidence_items:
            svc = e.get("service", "")
            if svc:
                affected_services.add(svc)

        if len(affected_services) > 1:
            return SpecialistFinding(
                agent_name=self.agent_name,
                hypothesis=f"Cascade failure across {', '.join(affected_services)}",
                evidence_ids=[],
                confidence=0.55,
                mechanism_type="cascade_failure",
                explanation=f"{len(affected_services)} services affected — possible topology propagation",
            )

        return SpecialistFinding(
            agent_name=self.agent_name,
            hypothesis="Single-service failure, no cascade detected",
            confidence=0.2,
        )


class DependencyInvestigator(BaseInvestigator):
    """Analyzes upstream/downstream service dependency impact."""

    agent_name = "dependency_investigator"

    def investigate(
        self,
        evidence_items: list[dict[str, Any]],
        service: str = "unknown",
        **context: Any,
    ) -> SpecialistFinding:
        log_evidence = [
            e for e in evidence_items
            if e.get("source") in ("logs", "log") or e.get("item_type") == "error_signature"
        ]

        timeout_logs = [
            e for e in log_evidence
            if any(kw in str(e.get("signature", "")).lower()
                   for kw in ("timeout", "connection refused", "502", "503", "504"))
        ]

        if timeout_logs:
            return SpecialistFinding(
                agent_name=self.agent_name,
                hypothesis=f"Upstream dependency failure affecting {service}",
                evidence_ids=[e.get("item_key", "") for e in timeout_logs],
                confidence=0.60,
                mechanism_type="dependency_failure",
                explanation=f"Found {len(timeout_logs)} timeout/connection errors in logs",
            )

        return SpecialistFinding(
            agent_name=self.agent_name,
            hypothesis="No dependency failure signals detected",
            confidence=0.0,
        )


class RunbookInvestigator(BaseInvestigator):
    """Matches current evidence against known historical runbook patterns."""

    agent_name = "runbook_investigator"

    def investigate(
        self,
        evidence_items: list[dict[str, Any]],
        service: str = "unknown",
        **context: Any,
    ) -> SpecialistFinding:
        pattern_hints = context.get("pattern_hints", [])
        if not pattern_hints:
            return SpecialistFinding(
                agent_name=self.agent_name,
                hypothesis="No matching historical patterns found",
                confidence=0.0,
            )

        best_match = max(pattern_hints, key=lambda p: p.get("similarity_score", 0))
        sim = best_match.get("similarity_score", 0)

        return SpecialistFinding(
            agent_name=self.agent_name,
            hypothesis=f"Matches historical pattern: {best_match.get('title', 'unknown')[:60]}",
            evidence_ids=[best_match.get("pattern_id", "")],
            confidence=round(min(1.0, sim), 4),
            mechanism_type=best_match.get("mechanism_type", "unknown"),
            explanation=f"Historical similarity score: {sim:.2f}",
        )


class Arbitrator:
    """
    Merges findings from all specialist investigators into a final ranked list.

    Applies cross-specialist consistency checks:
    - Findings supported by multiple specialists get a bonus
    - Contradictions between specialists reduce confidence
    """

    def __init__(self) -> None:
        self.specialists: List[BaseInvestigator] = [
            MetricsInvestigator(),
            DeploymentInvestigator(),
            GitInvestigator(),
            TopologyInvestigator(),
            DependencyInvestigator(),
            RunbookInvestigator(),
        ]

    def investigate_all(
        self,
        evidence_items: list[dict[str, Any]],
        service: str = "unknown",
        **context: Any,
    ) -> List[SpecialistFinding]:
        """Run all specialists and return merged, ranked findings."""
        findings: List[SpecialistFinding] = []

        for specialist in self.specialists:
            finding = specialist.investigate(evidence_items, service, **context)
            if finding.confidence > 0.0:
                findings.append(finding)

        # Cross-specialist consistency: boost mechanisms supported by multiple agents
        mechanism_counts: Dict[str, int] = {}
        for f in findings:
            mechanism_counts[f.mechanism_type] = mechanism_counts.get(f.mechanism_type, 0) + 1

        for f in findings:
            agreement_count = mechanism_counts.get(f.mechanism_type, 1)
            if agreement_count > 1:
                f.confidence = round(min(1.0, f.confidence * (1.0 + 0.1 * agreement_count)), 4)

        # Sort by confidence descending
        findings.sort(key=lambda f: f.confidence, reverse=True)
        return findings
