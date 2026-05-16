"""Replay consistency — detect drift between benchmark runs across time."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConsistencyResult:
    consistent: bool
    drift_score: float  # 0.0 = identical, 1.0 = completely diverged
    diverged_fields: list[str]
    contamination_flags: list[str]
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "consistent": self.consistent,
            "drift_score": self.drift_score,
            "diverged_fields": self.diverged_fields,
            "contamination_flags": self.contamination_flags,
            "recommendation": self.recommendation,
        }


_CONSISTENCY_THRESHOLD = 0.10  # >10% drift triggers inconsistency flag


class ReplayConsistencyChecker:
    """Compare two benchmark result snapshots and classify drift sources.

    Distinguishes:
    - Metric drift: numeric scores changed beyond tolerance
    - Structural drift: result schema changed
    - Contamination drift: scores improved suspiciously between runs
    - Seed drift: same seed, different results → hidden randomness
    """

    def check(
        self,
        baseline: dict[str, Any],
        current: dict[str, Any],
        tolerance: float = 0.02,
    ) -> ConsistencyResult:
        diverged: list[str] = []
        flags: list[str] = []

        metric_drift = self._compare_metrics(baseline, current, tolerance, diverged, flags)
        structural = self._compare_structure(baseline, current)
        if structural:
            flags.append("structural_schema_change")
            diverged.extend(structural)

        contamination = self._detect_contamination(baseline, current)
        if contamination:
            flags.append("suspicious_score_inflation")

        drift_score = min(1.0, metric_drift + (0.2 if structural else 0.0) + (0.3 if contamination else 0.0))
        consistent = drift_score <= _CONSISTENCY_THRESHOLD and not flags

        if drift_score == 0.0:
            recommendation = "Benchmark results are reproducible — no action needed."
        elif contamination:
            recommendation = "Score inflation detected. Verify no golden labels leaked into evaluation."
        elif structural:
            recommendation = "Schema changed. Re-run full benchmark suite from scratch with fresh dataset snapshot."
        else:
            recommendation = f"Metric drift {drift_score:.3f} within manageable range. Investigate: {', '.join(diverged[:3])}."

        return ConsistencyResult(
            consistent=consistent,
            drift_score=round(drift_score, 4),
            diverged_fields=diverged,
            contamination_flags=flags,
            recommendation=recommendation,
        )

    def check_seed_stability(
        self, run_a: dict[str, Any], run_b: dict[str, Any], seed_a: int, seed_b: int
    ) -> dict[str, Any]:
        """Same seed → results must be identical. Different seeds → differences are expected."""
        same_seed = seed_a == seed_b
        result = self.check(run_a, run_b, tolerance=0.0 if same_seed else 0.05)
        return {
            "same_seed": same_seed,
            "consistent": result.consistent,
            "seed_drift_violation": same_seed and not result.consistent,
            "drift_score": result.drift_score,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compare_metrics(
        self,
        a: dict[str, Any],
        b: dict[str, Any],
        tolerance: float,
        diverged: list[str],
        flags: list[str],
    ) -> float:
        total_drift = 0.0
        count = 0
        for key in set(a) | set(b):
            va, vb = a.get(key), b.get(key)
            if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
                delta = abs(float(va) - float(vb))
                rel = delta / max(abs(float(va)), 1e-9)
                if rel > tolerance:
                    diverged.append(f"{key}:{va:.4f}->{vb:.4f}")
                total_drift += rel
                count += 1
        return total_drift / count if count else 0.0

    def _compare_structure(self, a: dict[str, Any], b: dict[str, Any]) -> list[str]:
        a_keys = set(a.keys())
        b_keys = set(b.keys())
        return [f"missing:{k}" for k in a_keys - b_keys] + [f"added:{k}" for k in b_keys - a_keys]

    def _detect_contamination(self, baseline: dict[str, Any], current: dict[str, Any]) -> bool:
        numeric_keys = [k for k in set(baseline) & set(current) if isinstance(baseline[k], (int, float))]
        if not numeric_keys:
            return False
        improvements = sum(
            1 for k in numeric_keys if float(current.get(k, 0)) > float(baseline.get(k, 0)) * 1.15
        )
        # ≥50% of metrics improved by >15% in one run is suspicious
        return improvements >= max(1, len(numeric_keys) // 2)
