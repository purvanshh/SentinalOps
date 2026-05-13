"""
Deterministic fallback classifier for incident routing.

Zero external dependencies. Activates when ALL LLM providers are exhausted.
Uses keyword matching and heuristic rules to classify incidents into:
  latency, cpu, memory, deployment, database, networking, unknown

This is Layer 4 - the last resort before total failure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FallbackClassification:
    """Result of deterministic classification."""

    incident_type: str
    severity: str
    confidence: float
    requires_immediate_investigation: bool
    recommended_workflow: str
    rationale: str
    fallback: bool = True
    provider_used: str = "deterministic_fallback"


# ---------------------------------------------------------------------------
# Keyword rule definitions - order matters (first match wins within a category)
# ---------------------------------------------------------------------------


@dataclass
class _ClassificationRule:
    incident_type: str
    keywords: list[str] = field(default_factory=list)
    patterns: list[re.Pattern[str]] = field(default_factory=list)
    severity_boost_keywords: list[str] = field(default_factory=list)
    recommended_workflow: str = "full_investigation"


_RULES: list[_ClassificationRule] = [
    _ClassificationRule(
        incident_type="latency",
        keywords=[
            "latency",
            "slow",
            "timeout",
            "response time",
            "p99",
            "p95",
            "p50",
            "high latency",
            "request duration",
            "ttfb",
            "time to first byte",
            "connection timeout",
            "read timeout",
            "gateway timeout",
            "504",
            "deadline exceeded",
            "context deadline",
        ],
        patterns=[
            re.compile(r"p\d{2}\s*(>|above|exceeded)", re.IGNORECASE),
            re.compile(r"latency\s*(spike|increase|elevated)", re.IGNORECASE),
            re.compile(r"(response|request)\s*time\s*(high|elevated|spike)", re.IGNORECASE),
            re.compile(r"timeout\s*(error|exceeded|hit)", re.IGNORECASE),
        ],
        severity_boost_keywords=["spike", "critical", "outage", "down"],
        recommended_workflow="full_investigation",
    ),
    _ClassificationRule(
        incident_type="cpu",
        keywords=[
            "cpu",
            "processor",
            "cpu usage",
            "cpu utilization",
            "load average",
            "high cpu",
            "cpu throttling",
            "cpu saturation",
            "compute",
            "cpu steal",
            "runaway process",
            "cpu bound",
        ],
        patterns=[
            re.compile(
                r"cpu\s*(usage|utilization|load)\s*(high|above|exceeded|spike)", re.IGNORECASE
            ),
            re.compile(r"load\s*average\s*(high|above|critical)", re.IGNORECASE),
            re.compile(r"cpu\s*>\s*\d+%", re.IGNORECASE),
        ],
        severity_boost_keywords=["100%", "throttl", "saturat", "critical"],
        recommended_workflow="full_investigation",
    ),
    _ClassificationRule(
        incident_type="memory",
        keywords=[
            "memory",
            "oom",
            "out of memory",
            "memory leak",
            "heap",
            "ram",
            "memory pressure",
            "memory exhaustion",
            "gc pressure",
            "garbage collection",
            "swap",
            "memory limit",
            "oom kill",
            "oomkilled",
            "memory saturation",
        ],
        patterns=[
            re.compile(
                r"(memory|heap)\s*(usage|utilization|pressure)\s*(high|above|critical|spike)",
                re.IGNORECASE,
            ),
            re.compile(r"oom\s*(kill|killed|error)", re.IGNORECASE),
            re.compile(r"memory\s*>\s*\d+%", re.IGNORECASE),
            re.compile(r"(swap|page)\s*(usage|fault)", re.IGNORECASE),
        ],
        severity_boost_keywords=["oom", "kill", "exhausted", "critical", "leak"],
        recommended_workflow="full_investigation",
    ),
    _ClassificationRule(
        incident_type="deployment",
        keywords=[
            "deploy",
            "deployment",
            "rollout",
            "release",
            "canary",
            "rollback",
            "version",
            "build",
            "ci/cd",
            "pipeline",
            "helm",
            "kubernetes",
            "container",
            "image",
            "pod restart",
            "crashloopbackoff",
            "imagepullbackoff",
            "failed deploy",
            "deploy failure",
            "regression",
            "new version",
            "upgrade",
        ],
        patterns=[
            re.compile(r"deploy(ment)?\s*(fail|error|issue|regression)", re.IGNORECASE),
            re.compile(r"(after|since|following)\s*(deploy|release|rollout)", re.IGNORECASE),
            re.compile(r"(new|latest)\s*(version|build|release)", re.IGNORECASE),
            re.compile(r"(pod|container)\s*(restart|crash|fail)", re.IGNORECASE),
            re.compile(r"crashloopbackoff|imagepullbackoff", re.IGNORECASE),
        ],
        severity_boost_keywords=["crash", "fail", "rollback", "critical", "production"],
        recommended_workflow="full_investigation",
    ),
    _ClassificationRule(
        incident_type="database",
        keywords=[
            "database",
            "db",
            "postgres",
            "mysql",
            "redis",
            "mongo",
            "sql",
            "query",
            "connection pool",
            "deadlock",
            "replication lag",
            "slow query",
            "lock contention",
            "table lock",
            "connection refused",
            "max connections",
            "pool exhausted",
            "transaction",
            "disk full",
            "wal",
            "vacuum",
        ],
        patterns=[
            re.compile(r"(database|db)\s*(connection|error|timeout|slow|down)", re.IGNORECASE),
            re.compile(r"(connection\s*pool|pool)\s*(exhaust|full|timeout)", re.IGNORECASE),
            re.compile(r"(replication|replica)\s*(lag|delay|behind)", re.IGNORECASE),
            re.compile(r"(deadlock|lock\s*contention|lock\s*timeout)", re.IGNORECASE),
            re.compile(r"(slow|long)\s*quer(y|ies)", re.IGNORECASE),
        ],
        severity_boost_keywords=["deadlock", "down", "exhausted", "full", "critical"],
        recommended_workflow="full_investigation",
    ),
    _ClassificationRule(
        incident_type="networking",
        keywords=[
            "network",
            "dns",
            "connection refused",
            "connection reset",
            "packet loss",
            "unreachable",
            "connectivity",
            "firewall",
            "load balancer",
            "ssl",
            "tls",
            "certificate",
            "502",
            "503",
            "bad gateway",
            "service unavailable",
            "network partition",
            "split brain",
            "routing",
            "ingress",
            "egress",
        ],
        patterns=[
            re.compile(r"(network|connectivity)\s*(issue|error|failure|timeout)", re.IGNORECASE),
            re.compile(r"(dns|domain)\s*(resolution|lookup)\s*(fail|timeout|error)", re.IGNORECASE),
            re.compile(r"(connection|conn)\s*(refused|reset|timeout|closed)", re.IGNORECASE),
            re.compile(r"(502|503|bad gateway|service unavailable)", re.IGNORECASE),
            re.compile(r"(packet|data)\s*loss", re.IGNORECASE),
            re.compile(r"(ssl|tls|cert)\s*(error|expir|invalid)", re.IGNORECASE),
        ],
        severity_boost_keywords=["partition", "unreachable", "down", "critical", "outage"],
        recommended_workflow="full_investigation",
    ),
    _ClassificationRule(
        incident_type="infrastructure",
        keywords=[
            "node",
            "host",
            "disk",
            "filesystem",
            "storage",
            "iops",
            "inode",
            "instance",
            "vm",
            "kernel",
            "os",
            "systemd",
            "daemon",
            "pod evicted",
            "eviction",
            "pressure",
            "not ready",
            "degraded host",
            "hardware",
        ],
        patterns=[
            re.compile(r"(disk|filesystem|storage)\s*(full|usage|pressure|error)", re.IGNORECASE),
            re.compile(
                r"(node|host|instance)\s*(not ready|unavailable|degraded|down)", re.IGNORECASE
            ),
            re.compile(r"(inode|iops)\s*(high|exceeded|critical)", re.IGNORECASE),
            re.compile(r"(evict|pressure)\s*(memory|disk|node)?", re.IGNORECASE),
        ],
        severity_boost_keywords=["down", "critical", "full", "not ready", "evict"],
        recommended_workflow="full_investigation",
    ),
]


class DeterministicFallbackClassifier:
    """
    Rule-based incident classifier. Zero external dependencies.
    Deterministic, fast, resilient.

    Scoring:
    - Each keyword match: +1 point
    - Each regex pattern match: +2 points
    - Highest scoring category wins
    - Confidence derived from score relative to threshold
    """

    def __init__(self) -> None:
        self._rules = _RULES

    def classify(self, alert_payload: dict[str, Any]) -> FallbackClassification:
        """Classify an incident using deterministic rules."""
        text = self._extract_searchable_text(alert_payload)
        text_lower = text.lower()

        scores: dict[str, int] = {}
        matched_rule: _ClassificationRule | None = None
        max_score = 0

        for rule in self._rules:
            score = self._score_rule(rule, text_lower, text)
            scores[rule.incident_type] = score
            if score > max_score:
                max_score = score
                matched_rule = rule

        if matched_rule is None or max_score == 0:
            return self._unknown_classification(alert_payload)

        # Determine severity
        severity = self._determine_severity(alert_payload, matched_rule, text_lower)

        # Confidence: scale from 0.3 (minimum for fallback) to 0.7 (max for deterministic)
        confidence = min(0.3 + (max_score * 0.05), 0.7)

        requires_immediate = severity in ("critical", "high") or any(
            kw in text_lower for kw in ("outage", "down", "critical", "emergency")
        )

        return FallbackClassification(
            incident_type=matched_rule.incident_type,
            severity=severity,
            confidence=round(confidence, 2),
            requires_immediate_investigation=requires_immediate,
            recommended_workflow=matched_rule.recommended_workflow,
            rationale=(
                f"Deterministic fallback: matched {max_score} signals"
                f" for '{matched_rule.incident_type}'."
                f" Scores: {scores}. LLM providers exhausted."
            ),
        )

    def _score_rule(self, rule: _ClassificationRule, text_lower: str, text: str) -> int:
        score = 0
        for keyword in rule.keywords:
            if keyword in text_lower:
                score += 1
        for pattern in rule.patterns:
            if pattern.search(text):
                score += 2
        return score

    def _determine_severity(
        self, alert_payload: dict[str, Any], rule: _ClassificationRule, text_lower: str
    ) -> str:
        # Check if severity is already provided in the payload
        raw_severity = str(alert_payload.get("severity", "")).lower().strip()
        if raw_severity in ("critical", "high", "medium", "low"):
            return raw_severity

        # Heuristic: check for severity boost keywords
        boost_count = sum(1 for kw in rule.severity_boost_keywords if kw in text_lower)
        if boost_count >= 2:
            return "high"
        if boost_count >= 1:
            return "medium"
        return "medium"

    def _unknown_classification(self, alert_payload: dict[str, Any]) -> FallbackClassification:
        raw_severity = str(alert_payload.get("severity", "medium")).lower().strip()
        valid = ("critical", "high", "medium", "low")
        severity = raw_severity if raw_severity in valid else "medium"

        return FallbackClassification(
            incident_type="unknown",
            severity=severity,
            confidence=0.1,
            requires_immediate_investigation=severity in ("critical", "high"),
            recommended_workflow="human_triage",
            rationale=(
                "Deterministic fallback: no classification rules matched."
                " Routing to human triage."
            ),
        )

    def _extract_searchable_text(self, alert_payload: dict[str, Any]) -> str:
        """Extract all text content from the alert payload for matching."""
        parts: list[str] = []
        for key in ("title", "summary", "description", "message", "alertname", "alert_name"):
            val = alert_payload.get(key)
            if val and isinstance(val, str):
                parts.append(val)

        # Extract from labels/annotations (common in Prometheus alerts)
        for container_key in ("labels", "annotations"):
            container = alert_payload.get(container_key)
            if isinstance(container, dict):
                for val in container.values():
                    if isinstance(val, str):
                        parts.append(val)

        # Extract from raw_payload if present
        raw = alert_payload.get("raw_payload")
        if isinstance(raw, dict):
            for key in ("title", "summary", "description", "message"):
                val = raw.get(key)
                if val and isinstance(val, str):
                    parts.append(val)

        return " ".join(parts) if parts else ""
