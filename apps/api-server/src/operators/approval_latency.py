"""
Approval latency analysis for SentinelOps Phase 47.

Measures and analyzes how long operators take to approve or reject
AI recommendations, segmented by severity, mechanism, and operator.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime

from operators.intervention_tracker import OperatorIntervention


@dataclass
class LatencySample:
    """Latency between AI recommendation and operator response."""

    intervention_id: str
    incident_id: str
    operator_id: str
    kind: str
    ai_recommendation: str
    latency_seconds: float
    severity: str = "info"
    mechanism: str = ""


@dataclass
class LatencyReport:
    """Summary statistics for operator approval/rejection latency."""

    total_samples: int
    mean_latency_seconds: float
    median_latency_seconds: float
    p90_latency_seconds: float
    min_latency_seconds: float
    max_latency_seconds: float
    by_kind: dict[str, float]  # kind → mean latency
    by_severity: dict[str, float]
    slow_threshold_seconds: float
    slow_rate: float  # fraction above slow_threshold

    @property
    def is_responsive(self) -> bool:
        return self.mean_latency_seconds <= self.slow_threshold_seconds


class ApprovalLatencyAnalyzer:
    """
    Computes operator response latency from paired (recommendation, intervention) records.

    Uses the intervention timestamp and a provided AI-recommendation-emission
    timestamp to compute latency. When the AI timestamp is unavailable, falls
    back to 0.0 latency (not counted in percentile statistics).
    """

    _DEFAULT_SLOW_THRESHOLD: float = 300.0  # 5 minutes

    def __init__(self, slow_threshold_seconds: float = _DEFAULT_SLOW_THRESHOLD) -> None:
        self._slow_threshold = slow_threshold_seconds
        self._samples: list[LatencySample] = []

    def ingest(
        self,
        intervention: OperatorIntervention,
        ai_emit_timestamp_iso: str,
        severity: str = "info",
    ) -> LatencySample | None:
        """Compute latency for one intervention vs. when AI emitted the recommendation."""
        latency = self._compute_latency(ai_emit_timestamp_iso, intervention.timestamp_iso)
        if latency < 0:
            return None

        sample = LatencySample(
            intervention_id=intervention.intervention_id,
            incident_id=intervention.incident_id,
            operator_id=intervention.operator_id,
            kind=intervention.kind.value,
            ai_recommendation=intervention.ai_recommendation,
            latency_seconds=latency,
            severity=severity,
            mechanism=intervention.target_mechanism,
        )
        self._samples.append(sample)
        return sample

    def ingest_batch(
        self,
        pairs: list[tuple[OperatorIntervention, str, str]],
    ) -> list[LatencySample]:
        """Ingest multiple (intervention, ai_timestamp, severity) triples."""
        out: list[LatencySample] = []
        for iv, ts, sev in pairs:
            sample = self.ingest(iv, ts, sev)
            if sample is not None:
                out.append(sample)
        return out

    def report(self) -> LatencyReport:
        samples = self._samples
        n = len(samples)
        if n == 0:
            return LatencyReport(
                total_samples=0,
                mean_latency_seconds=0.0,
                median_latency_seconds=0.0,
                p90_latency_seconds=0.0,
                min_latency_seconds=0.0,
                max_latency_seconds=0.0,
                by_kind={},
                by_severity={},
                slow_threshold_seconds=self._slow_threshold,
                slow_rate=0.0,
            )

        latencies = sorted(s.latency_seconds for s in samples)
        mean = statistics.mean(latencies)
        median = statistics.median(latencies)
        p90_idx = int(len(latencies) * 0.90)
        p90 = latencies[min(p90_idx, len(latencies) - 1)]

        by_kind = self._mean_by(samples, key=lambda s: s.kind)
        by_sev = self._mean_by(samples, key=lambda s: s.severity)
        slow = sum(1 for s in samples if s.latency_seconds > self._slow_threshold)

        return LatencyReport(
            total_samples=n,
            mean_latency_seconds=mean,
            median_latency_seconds=median,
            p90_latency_seconds=p90,
            min_latency_seconds=latencies[0],
            max_latency_seconds=latencies[-1],
            by_kind=by_kind,
            by_severity=by_sev,
            slow_threshold_seconds=self._slow_threshold,
            slow_rate=slow / n,
        )

    def per_operator_report(self) -> dict[str, LatencyReport]:
        """Individual latency report per operator."""
        by_op: dict[str, list[LatencySample]] = {}
        for s in self._samples:
            by_op.setdefault(s.operator_id, []).append(s)

        results: dict[str, LatencyReport] = {}
        for op, samples in by_op.items():
            analyzer = ApprovalLatencyAnalyzer(self._slow_threshold)
            analyzer._samples = samples
            results[op] = analyzer.report()
        return results

    def clear(self) -> None:
        self._samples.clear()

    # ------------------------------------------------------------------

    @staticmethod
    def _compute_latency(t0_iso: str, t1_iso: str) -> float:
        try:
            t0 = _parse_iso(t0_iso)
            t1 = _parse_iso(t1_iso)
            return (t1 - t0).total_seconds()
        except Exception:
            return -1.0

    @staticmethod
    def _mean_by(samples: list[LatencySample], key) -> dict[str, float]:
        groups: dict[str, list[float]] = {}
        for s in samples:
            k = key(s)
            groups.setdefault(k, []).append(s.latency_seconds)
        return {k: statistics.mean(vs) for k, vs in groups.items()}


def _parse_iso(ts: str) -> datetime:
    ts = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(ts)
