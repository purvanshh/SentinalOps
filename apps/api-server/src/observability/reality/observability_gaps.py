"""
Observability gap detection for Phase 48 operational realism.

Detects structural holes in telemetry that would impair diagnosis:
  - Missing metric data (can't identify quantitative thresholds)
  - Missing logs (can't establish error context)
  - Missing alert (incident may have had no automated detection)
  - Dead streams (metrics present but frozen — METRIC_FREEZE pattern)
  - Blackout windows (gap > threshold between consecutive events)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class GapKind(str, Enum):
    MISSING_METRICS = "missing_metrics"
    MISSING_LOGS = "missing_logs"
    MISSING_ALERTS = "missing_alerts"
    DEAD_METRIC_STREAM = "dead_metric_stream"
    TELEMETRY_BLACKOUT = "telemetry_blackout"
    STALE_REPLAY = "stale_replay"
    DUPLICATE_FLOOD = "duplicate_flood"


@dataclass
class ObservabilityGap:
    kind: GapKind
    description: str
    severity: str  # "low" | "medium" | "high"
    confidence_impact: float  # how much this gap should reduce root-cause confidence


@dataclass
class GapReport:
    gaps: list[ObservabilityGap]
    gap_count: int
    high_severity_gaps: int
    total_confidence_penalty: float  # sum of confidence_impact, capped at 0.60

    def has_gaps(self) -> bool:
        return self.gap_count > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "gap_count": self.gap_count,
            "high_severity_gaps": self.high_severity_gaps,
            "total_confidence_penalty": round(self.total_confidence_penalty, 4),
            "gaps": [
                {
                    "kind": g.kind.value,
                    "description": g.description,
                    "severity": g.severity,
                    "confidence_impact": g.confidence_impact,
                }
                for g in self.gaps
            ],
        }


_BLACKOUT_THRESHOLD_SECONDS = 300  # 5-minute gap = blackout


def _parse_ts(ts: str) -> float | None:
    if not ts:
        return None
    try:
        from datetime import datetime

        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.timestamp()
    except (ValueError, AttributeError):
        return None


class ObservabilityGapDetector:
    """Detects structural telemetry gaps that impair root-cause diagnosis."""

    def detect(self, events: list[dict[str, Any]]) -> GapReport:
        gaps: list[ObservabilityGap] = []

        kinds = {ev.get("kind", "") for ev in events}

        # Missing metric coverage
        if "metric" not in kinds:
            gaps.append(
                ObservabilityGap(
                    kind=GapKind.MISSING_METRICS,
                    description="No metric events in telemetry stream",
                    severity="high",
                    confidence_impact=0.20,
                )
            )

        # Missing log coverage
        if "log" not in kinds:
            gaps.append(
                ObservabilityGap(
                    kind=GapKind.MISSING_LOGS,
                    description="No log events in telemetry stream",
                    severity="medium",
                    confidence_impact=0.15,
                )
            )

        # Missing alert
        if "alert" not in kinds:
            gaps.append(
                ObservabilityGap(
                    kind=GapKind.MISSING_ALERTS,
                    description="No alert events; automated detection may have been absent",
                    severity="medium",
                    confidence_impact=0.10,
                )
            )

        # Stale replay detection
        stale_count = sum(1 for ev in events if ev.get("_stale_replay"))
        if stale_count > 0 and len(events) > 0:
            frac = stale_count / len(events)
            if frac >= 0.20:
                gaps.append(
                    ObservabilityGap(
                        kind=GapKind.STALE_REPLAY,
                        description=(
                            f"{stale_count} events ({frac:.0%}) are backdated stale replays"
                        ),
                        severity="high",
                        confidence_impact=0.20,
                    )
                )

        # Duplicate flood
        dup_count = sum(1 for ev in events if ev.get("_duplicate"))
        if dup_count > 0 and len(events) > 0:
            dup_frac = dup_count / len(events)
            if dup_frac >= 0.30:
                gaps.append(
                    ObservabilityGap(
                        kind=GapKind.DUPLICATE_FLOOD,
                        description=f"{dup_frac:.0%} of events are duplicates (alert storm)",
                        severity="medium",
                        confidence_impact=0.10,
                    )
                )

        # Blackout window detection (gap > threshold between consecutive events)
        timestamps = sorted(
            t for t in (_parse_ts(ev.get("timestamp_iso", "")) for ev in events) if t is not None
        )
        if len(timestamps) >= 2:
            for i in range(1, len(timestamps)):
                gap_s = timestamps[i] - timestamps[i - 1]
                if gap_s > _BLACKOUT_THRESHOLD_SECONDS:
                    gaps.append(
                        ObservabilityGap(
                            kind=GapKind.TELEMETRY_BLACKOUT,
                            description=f"Telemetry gap of {gap_s:.0f}s detected",
                            severity="high",
                            confidence_impact=0.15,
                        )
                    )
                    break  # report only the first

        high_sev = sum(1 for g in gaps if g.severity == "high")
        penalty = min(0.60, sum(g.confidence_impact for g in gaps))

        return GapReport(
            gaps=gaps,
            gap_count=len(gaps),
            high_severity_gaps=high_sev,
            total_confidence_penalty=round(penalty, 4),
        )
