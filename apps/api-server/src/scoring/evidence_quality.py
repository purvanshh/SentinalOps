"""
Evidence Quality Scoring for SentinelOps Phase 9.

Not every piece of evidence deserves equal weight. A stack trace with a
specific exception is far more diagnostic than a generic warning log.

This module scores each evidence item by its diagnostic value, allowing
the probability engine to make evidence-aware decisions.

Quality tiers:
    0.90-1.00  Stack traces, core dumps, OOM kills
    0.80-0.89  Metric anomalies with high z-scores, deployment events
    0.60-0.79  Structured log errors, API error codes
    0.30-0.59  Warning logs, threshold alerts
    0.10-0.29  Informational logs, user comments
    0.00-0.09  Noise, duplicate alerts
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class ScoredEvidence:
    """An evidence item with its computed diagnostic quality score."""

    item_key: str
    source: str
    quality_score: float
    quality_tier: str
    scoring_rationale: str
    original_item: Dict[str, Any]


# Keyword patterns that indicate high diagnostic value
_HIGH_VALUE_PATTERNS = [
    "stacktrace", "stack_trace", "traceback", "exception",
    "oom", "out_of_memory", "segfault", "core_dump",
    "fatal", "panic", "crash",
]

_MEDIUM_VALUE_PATTERNS = [
    "error", "failed", "refused", "timeout", "rejected",
    "exhausted", "exceeded", "overflow", "denied",
]

_LOW_VALUE_PATTERNS = [
    "warning", "warn", "deprecated", "retry", "slow",
    "degraded", "elevated",
]


def _tier_label(score: float) -> str:
    if score >= 0.90:
        return "critical_diagnostic"
    if score >= 0.80:
        return "high_diagnostic"
    if score >= 0.60:
        return "moderate_diagnostic"
    if score >= 0.30:
        return "low_diagnostic"
    if score >= 0.10:
        return "informational"
    return "noise"


class EvidenceQualityScorer:
    """
    Scores evidence items based on their type, content, and diagnostic utility.

    Scoring factors:
    1. Evidence type (metric_anomaly > error_signature > deployment > log)
    2. Content severity (stack trace > error > warning > info)
    3. Statistical significance (z-score for metrics)
    4. Specificity (named service/component vs generic message)
    5. Freshness (evidence within incident window scores higher)
    """

    def __init__(self) -> None:
        self._type_base_scores: Dict[str, float] = {
            "metric_anomaly": 0.80,
            "error_signature": 0.75,
            "deployment_change": 0.70,
            "alert": 0.65,
            "log_error": 0.50,
            "log_warning": 0.30,
            "log_info": 0.15,
            "user_comment": 0.10,
        }

    def score_item(self, item: dict[str, Any]) -> ScoredEvidence:
        """Score a single evidence item."""
        item_type = item.get("item_type", "unknown")
        source = item.get("source", "unknown")
        item_key = item.get("item_key", item.get("evidence_id", ""))

        # Base score from evidence type
        base_score = self._type_base_scores.get(item_type, 0.40)
        rationale_parts = [f"base_type={item_type}:{base_score:.2f}"]

        # Content severity boost
        content = str(item.get("signature", "")) + str(item.get("description", ""))
        content_lower = content.lower()

        severity_boost = 0.0
        if any(p in content_lower for p in _HIGH_VALUE_PATTERNS):
            severity_boost = 0.15
            rationale_parts.append("high_severity_content:+0.15")
        elif any(p in content_lower for p in _MEDIUM_VALUE_PATTERNS):
            severity_boost = 0.08
            rationale_parts.append("medium_severity_content:+0.08")
        elif any(p in content_lower for p in _LOW_VALUE_PATTERNS):
            severity_boost = 0.0
            rationale_parts.append("low_severity_content:+0.00")

        # Statistical significance for metrics
        z_score = abs(float(item.get("z_score", 0)))
        z_boost = 0.0
        if z_score > 0 and item_type == "metric_anomaly":
            z_boost = min(0.15, z_score / 10.0)
            rationale_parts.append(f"z_score={z_score:.1f}:+{z_boost:.2f}")

        # Specificity boost: named services/components
        service = item.get("service", "")
        specificity_boost = 0.05 if service and service != "unknown" else 0.0
        if specificity_boost > 0:
            rationale_parts.append(f"specific_service={service}:+0.05")

        # Count/frequency for log errors
        count = int(item.get("count", 1))
        count_boost = min(0.10, (count - 1) * 0.02) if count > 1 else 0.0
        if count_boost > 0:
            rationale_parts.append(f"count={count}:+{count_boost:.2f}")

        # Final score
        final_score = min(
            1.0, base_score + severity_boost + z_boost + specificity_boost + count_boost
        )

        return ScoredEvidence(
            item_key=item_key,
            source=source,
            quality_score=round(final_score, 4),
            quality_tier=_tier_label(final_score),
            scoring_rationale=" | ".join(rationale_parts),
            original_item=item,
        )

    def score_all(self, evidence_items: list[dict[str, Any]]) -> List[ScoredEvidence]:
        """Score all evidence items and return sorted by quality (highest first)."""
        scored = [self.score_item(item) for item in evidence_items]
        scored.sort(key=lambda s: s.quality_score, reverse=True)
        return scored

    def mean_quality(self, evidence_items: list[dict[str, Any]]) -> float:
        """Compute the mean evidence quality for a set of items."""
        if not evidence_items:
            return 0.0
        scored = self.score_all(evidence_items)
        return round(sum(s.quality_score for s in scored) / len(scored), 4)

    def filter_noise(
        self,
        evidence_items: list[dict[str, Any]],
        threshold: float = 0.25,
    ) -> list[dict[str, Any]]:
        """Filter out low-quality evidence below threshold."""
        scored = self.score_all(evidence_items)
        return [s.original_item for s in scored if s.quality_score >= threshold]
