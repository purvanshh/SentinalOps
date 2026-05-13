"""
Phase 39 benchmark suite loader and validator.

Loads the 106-incident labeled evaluation suite from benchmark_suite_v1.json.
Provides typed access to benchmark incidents for deterministic replay.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SUITE_FILE = (
    Path(__file__).parent.parent.parent.parent.parent
    / "simulation"
    / "datasets"
    / "evaluation"
    / "benchmark_suite_v1.json"
)

REMEDIATION_CLASSES = frozenset(
    {
        "SAFE_AND_CORRECT",
        "SAFE_BUT_USELESS",
        "PARTIALLY_CORRECT",
        "DANGEROUS",
        "HALLUCINATED",
        "OPERATIONALLY_INVALID",
    }
)

RISK_TIERS = frozenset({"LOW", "MODERATE", "HIGH", "CRITICAL"})
OPERATOR_ACTIONS = frozenset({"APPROVE", "REJECT", "ESCALATE", "IGNORE"})


@dataclass
class BenchmarkIncident:
    id: str
    name: str
    version: str
    category: str
    description: str
    alert_payload: dict[str, Any]
    metrics_snapshot: list[dict[str, Any]]
    logs_sample: list[dict[str, Any]]
    mocked_tool_responses: dict[str, Any]
    golden_classification: str
    golden_severity: str
    golden_root_cause: str
    golden_remediation: str
    golden_remediation_class: str
    golden_expected_blast_radius_mean: int
    golden_remediation_safe: bool
    golden_operator_action: str
    expected_confidence_range: list[float]
    is_noisy_alert: bool
    is_false_positive: bool
    requires_escalation: bool
    risk_tier: str

    @property
    def confidence_min(self) -> float:
        return self.expected_confidence_range[0]

    @property
    def confidence_max(self) -> float:
        return self.expected_confidence_range[1]

    @property
    def confidence_midpoint(self) -> float:
        return (self.confidence_min + self.confidence_max) / 2

    @property
    def mocked_confidence(self) -> float:
        return self.mocked_tool_responses.get("router", {}).get(
            "confidence", self.confidence_midpoint
        )

    def to_runner_format(self) -> dict[str, Any]:
        """Produce the dict format expected by evaluation/runner.py."""
        return {
            "name": self.name,
            "alert_payload": self.alert_payload,
            "mocked_tool_responses": self.mocked_tool_responses,
            "golden_classification": self.golden_classification,
            "golden_root_cause": self.golden_root_cause,
            "golden_expected_blast_radius_mean": self.golden_expected_blast_radius_mean,
            "golden_remediation_safe": self.golden_remediation_safe,
        }


@dataclass
class BenchmarkSuite:
    suite_id: str
    version: str
    created: str
    description: str
    total_incidents: int
    categories: list[str]
    incidents: list[BenchmarkIncident] = field(default_factory=list)

    def by_category(self, category: str) -> list[BenchmarkIncident]:
        return [i for i in self.incidents if i.category == category]

    def by_remediation_class(self, cls: str) -> list[BenchmarkIncident]:
        return [i for i in self.incidents if i.golden_remediation_class == cls]

    def dangerous_incidents(self) -> list[BenchmarkIncident]:
        return self.by_remediation_class("DANGEROUS")

    def hallucinated_incidents(self) -> list[BenchmarkIncident]:
        return self.by_remediation_class("HALLUCINATED")

    def false_positives(self) -> list[BenchmarkIncident]:
        return [i for i in self.incidents if i.is_false_positive]

    def requires_escalation_incidents(self) -> list[BenchmarkIncident]:
        return [i for i in self.incidents if i.requires_escalation]

    def low_confidence_incidents(self) -> list[BenchmarkIncident]:
        return [i for i in self.incidents if i.confidence_max < 0.65]


def _parse_incident(raw: dict[str, Any]) -> BenchmarkIncident:
    return BenchmarkIncident(
        id=raw["id"],
        name=raw["name"],
        version=raw.get("version", "1.0"),
        category=raw["category"],
        description=raw.get("description", ""),
        alert_payload=raw["alert_payload"],
        metrics_snapshot=raw.get("metrics_snapshot", []),
        logs_sample=raw.get("logs_sample", []),
        mocked_tool_responses=raw["mocked_tool_responses"],
        golden_classification=raw["golden_classification"],
        golden_severity=raw.get("golden_severity", raw["alert_payload"].get("severity", "medium")),
        golden_root_cause=raw["golden_root_cause"],
        golden_remediation=raw.get("golden_remediation", ""),
        golden_remediation_class=raw.get("golden_remediation_class", "SAFE_AND_CORRECT"),
        golden_expected_blast_radius_mean=raw["golden_expected_blast_radius_mean"],
        golden_remediation_safe=raw["golden_remediation_safe"],
        golden_operator_action=raw.get("golden_operator_action", "APPROVE"),
        expected_confidence_range=raw.get("expected_confidence_range", [0.5, 0.9]),
        is_noisy_alert=raw.get("is_noisy_alert", False),
        is_false_positive=raw.get("is_false_positive", False),
        requires_escalation=raw.get("requires_escalation", False),
        risk_tier=raw.get("risk_tier", "MODERATE"),
    )


def load_benchmark_suite(path: Path | None = None) -> BenchmarkSuite:
    suite_path = path or SUITE_FILE
    raw = json.loads(suite_path.read_text())
    incidents = [_parse_incident(inc) for inc in raw["incidents"]]
    return BenchmarkSuite(
        suite_id=raw["suite_id"],
        version=raw["version"],
        created=raw["created"],
        description=raw["description"],
        total_incidents=raw["total_incidents"],
        categories=raw["categories"],
        incidents=incidents,
    )


def validate_suite(suite: BenchmarkSuite) -> list[str]:
    """Return a list of validation errors. Empty list means suite is valid."""
    errors: list[str] = []
    seen_ids: set[str] = set()
    for inc in suite.incidents:
        if inc.id in seen_ids:
            errors.append(f"Duplicate incident id: {inc.id}")
        seen_ids.add(inc.id)
        if inc.golden_remediation_class not in REMEDIATION_CLASSES:
            errors.append(f"{inc.id}: invalid remediation_class '{inc.golden_remediation_class}'")
        if inc.risk_tier not in RISK_TIERS:
            errors.append(f"{inc.id}: invalid risk_tier '{inc.risk_tier}'")
        if inc.golden_operator_action not in OPERATOR_ACTIONS:
            errors.append(f"{inc.id}: invalid operator_action '{inc.golden_operator_action}'")
        if not (0.0 <= inc.confidence_min <= inc.confidence_max <= 1.0):
            errors.append(f"{inc.id}: invalid confidence_range {inc.expected_confidence_range}")
    return errors
