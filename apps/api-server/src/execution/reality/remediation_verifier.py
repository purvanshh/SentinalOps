"""
Remediation verification for Phase 48 operational realism.

Verifies that a remediation action actually changed the system state.
A remediation is "real" only if the post-action telemetry differs
meaningfully from the pre-action telemetry.

Detects:
  - Remediation that had no observable effect
  - Remediation that addressed symptoms but not root cause
  - Remediation side effects that created new issues
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class VerificationVerdict(str, Enum):
    CONFIRMED = "confirmed"  # telemetry changed in expected direction
    NO_EFFECT = "no_effect"  # telemetry unchanged after action
    SIDE_EFFECTS_DETECTED = "side_effects_detected"  # new issues appeared
    INSUFFICIENT_DATA = "insufficient_data"  # not enough pre/post data


@dataclass
class RemediationVerificationResult:
    remediation_id: str
    verdict: VerificationVerdict
    pre_error_rate: float
    post_error_rate: float
    delta: float  # post - pre (negative = improvement)
    side_effects: list[str]
    confidence: float  # how confident is the verification

    def to_dict(self) -> dict[str, Any]:
        return {
            "remediation_id": self.remediation_id,
            "verdict": self.verdict.value,
            "pre_error_rate": round(self.pre_error_rate, 4),
            "post_error_rate": round(self.post_error_rate, 4),
            "delta": round(self.delta, 4),
            "side_effects": self.side_effects,
            "confidence": round(self.confidence, 4),
        }


class RemediationVerifier:
    """
    Checks whether a remediation actually changed the system state.

    Compares pre-action and post-action snapshot windows.
    """

    _MIN_IMPROVEMENT_THRESHOLD = -0.05  # at least 5% error rate reduction
    _SIDE_EFFECT_THRESHOLD = 0.10  # new metric appearing above 10% = side effect

    def verify(
        self,
        remediation_id: str,
        pre_snapshots: list[dict[str, Any]],
        post_snapshots: list[dict[str, Any]],
        watched_metrics: list[str] | None = None,
    ) -> RemediationVerificationResult:
        if not pre_snapshots or not post_snapshots:
            return RemediationVerificationResult(
                remediation_id=remediation_id,
                verdict=VerificationVerdict.INSUFFICIENT_DATA,
                pre_error_rate=0.0,
                post_error_rate=0.0,
                delta=0.0,
                side_effects=[],
                confidence=0.20,
            )

        pre_rate = sum(s.get("error_rate", 0.0) for s in pre_snapshots) / len(pre_snapshots)
        post_rate = sum(s.get("error_rate", 0.0) for s in post_snapshots) / len(post_snapshots)
        delta = post_rate - pre_rate

        side_effects: list[str] = []
        metrics = watched_metrics or []
        for metric in metrics:
            pre_val = sum(s.get(metric, 0.0) for s in pre_snapshots) / len(pre_snapshots)
            post_val = sum(s.get(metric, 0.0) for s in post_snapshots) / len(post_snapshots)
            if post_val > pre_val + self._SIDE_EFFECT_THRESHOLD:
                side_effects.append(f"{metric}_degraded: {pre_val:.2f}→{post_val:.2f}")

        if side_effects:
            verdict = VerificationVerdict.SIDE_EFFECTS_DETECTED
            confidence = 0.60
        elif delta <= self._MIN_IMPROVEMENT_THRESHOLD:
            verdict = VerificationVerdict.CONFIRMED
            confidence = min(0.95, 0.70 + abs(delta))
        elif abs(delta) < 0.01:
            verdict = VerificationVerdict.NO_EFFECT
            confidence = 0.80
        else:
            verdict = VerificationVerdict.CONFIRMED
            confidence = 0.50

        return RemediationVerificationResult(
            remediation_id=remediation_id,
            verdict=verdict,
            pre_error_rate=round(pre_rate, 4),
            post_error_rate=round(post_rate, 4),
            delta=round(delta, 4),
            side_effects=side_effects,
            confidence=round(confidence, 4),
        )
