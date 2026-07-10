from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FailureSignature:
    signature_id: str
    name: str
    mechanism_type: str
    required_evidence_types: list[str] = field(default_factory=list)
    optional_evidence_types: list[str] = field(default_factory=list)
    confidence_weight: float = 1.0
    description: str = ""


class PatternStore:
    def __init__(self) -> None:
        self.signatures = [
            FailureSignature(
                signature_id="database_latency",
                name="Database Latency Spike",
                mechanism_type="dependency_failure",
                required_evidence_types=["metric_anomaly"],
                optional_evidence_types=["error_signature"],
                confidence_weight=0.85,
                description="High database query response times or connection pool exhaustion.",
            ),
            FailureSignature(
                signature_id="memory_pressure",
                name="Container Memory Pressure",
                mechanism_type="resource_exhaustion",
                required_evidence_types=["error_signature"],
                optional_evidence_types=["metric_anomaly"],
                confidence_weight=0.9,
                description="Container memory limit reached or OOM-kill event detected.",
            ),
            FailureSignature(
                signature_id="deployment_regression",
                name="Deployment Regression",
                mechanism_type="deployment_error",
                required_evidence_types=["deployment_change"],
                optional_evidence_types=["error_signature", "metric_anomaly"],
                confidence_weight=0.95,
                description=(
                    "Performance regression or error rate spike immediately following "
                    "a deployment."
                ),
            ),
            FailureSignature(
                signature_id="cascade_failure",
                name="Cascading Downstream Failure",
                mechanism_type="cascade_failure",
                required_evidence_types=["metric_anomaly", "error_signature"],
                optional_evidence_types=["deployment_change"],
                confidence_weight=0.8,
                description=(
                    "Failure in a downstream dependency causing failures in upstream services."
                ),
            ),
            FailureSignature(
                signature_id="config_drift",
                name="Configuration Drift",
                mechanism_type="configuration_drift",
                required_evidence_types=["deployment_change"],
                optional_evidence_types=[],
                confidence_weight=0.75,
                description="System behavior change due to environment configuration updates.",
            ),
        ]

    def get_signatures(self) -> list[FailureSignature]:
        return self.signatures

    def match_evidence(
        self, evidence_items: list[dict[str, Any]]
    ) -> list[tuple[FailureSignature, float]]:
        present_types = {item.get("item_type") for item in evidence_items if item.get("item_type")}
        results = []

        for sig in self.signatures:
            # If any required type is missing, score is 0.0
            req_missing = any(req not in present_types for req in sig.required_evidence_types)
            if req_missing:
                results.append((sig, 0.0))
                continue

            # Calculate match ratio
            matched_req = [req for req in sig.required_evidence_types if req in present_types]
            matched_opt = [opt for opt in sig.optional_evidence_types if opt in present_types]
            total_unique_types = len(set(sig.required_evidence_types + sig.optional_evidence_types))

            if total_unique_types == 0:
                score = 1.0
            else:
                score = (len(matched_req) + len(matched_opt)) / total_unique_types

            weighted_score = round(score * sig.confidence_weight, 4)
            results.append((sig, weighted_score))

        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results
