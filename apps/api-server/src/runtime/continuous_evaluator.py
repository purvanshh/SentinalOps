"""
Continuous evaluation runtime for SentinelOps Phase 47.

Manages incremental evaluation cycles: ingest records, compute windowed
metrics, emit drift alerts, and maintain a rolling evaluation state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from evaluation.live.longitudinal_metrics import (
    EvaluationRecord,
    LongitudinalEvaluator,
    LongitudinalReport,
)


@dataclass
class EvaluationCycle:
    """Results of one evaluation cycle."""

    cycle_id: int
    executed_at: str
    records_ingested: int
    total_records_seen: int
    report: LongitudinalReport
    alerts: list[str] = field(default_factory=list)

    @property
    def has_alerts(self) -> bool:
        return len(self.alerts) > 0


class ContinuousEvaluator:
    """
    Runs incremental evaluation cycles over a stream of EvaluationRecords.

    Each `run_cycle()` call ingests pending records, computes a fresh
    longitudinal report, checks for drift, and notifies registered handlers.
    """

    def __init__(
        self,
        window_size: int = 20,
        cycle_batch_size: int = 10,
        drift_threshold: float = 0.05,
    ) -> None:
        self._evaluator = LongitudinalEvaluator(window_size=window_size)
        self._cycle_batch_size = cycle_batch_size
        self._drift_threshold = drift_threshold
        self._pending: list[EvaluationRecord] = []
        self._cycle_count = 0
        self._total_seen = 0
        self._cycles: list[EvaluationCycle] = []
        self._alert_handlers: list[Callable[[EvaluationCycle], None]] = []

    def register_alert_handler(self, handler: Callable[[EvaluationCycle], None]) -> None:
        self._alert_handlers.append(handler)

    def ingest(self, record: EvaluationRecord) -> None:
        self._pending.append(record)

    def ingest_batch(self, records: list[EvaluationRecord]) -> None:
        self._pending.extend(records)

    def run_cycle(self) -> EvaluationCycle | None:
        """Process pending records and produce one evaluation cycle. Returns None if no pending."""
        if not self._pending:
            return None

        batch = self._pending[: self._cycle_batch_size]
        self._pending = self._pending[self._cycle_batch_size :]
        self._evaluator.ingest_batch(batch)
        self._total_seen += len(batch)
        self._cycle_count += 1

        report = self._evaluator.compute()
        alerts = self._detect_alerts(report)

        cycle = EvaluationCycle(
            cycle_id=self._cycle_count,
            executed_at=datetime.now(timezone.utc).isoformat(),
            records_ingested=len(batch),
            total_records_seen=self._total_seen,
            report=report,
            alerts=alerts,
        )
        self._cycles.append(cycle)

        if alerts:
            for handler in self._alert_handlers:
                handler(cycle)

        return cycle

    def run_all(self) -> list[EvaluationCycle]:
        """Drain all pending records, running cycles until the queue is empty."""
        cycles: list[EvaluationCycle] = []
        while self._pending:
            cycle = self.run_cycle()
            if cycle:
                cycles.append(cycle)
        return cycles

    def latest_report(self) -> LongitudinalReport | None:
        if not self._cycles:
            return None
        return self._cycles[-1].report

    def all_cycles(self) -> list[EvaluationCycle]:
        return list(self._cycles)

    def cycle_count(self) -> int:
        return self._cycle_count

    def pending_count(self) -> int:
        return len(self._pending)

    def reset(self) -> None:
        self._evaluator.reset()
        self._pending.clear()
        self._cycles.clear()
        self._cycle_count = 0
        self._total_seen = 0

    # ------------------------------------------------------------------

    def _detect_alerts(self, report: LongitudinalReport) -> list[str]:
        alerts: list[str] = []
        if report.drift and report.drift.drift_detected:
            alerts.append(
                f"drift_detected: direction={report.drift.drift_direction} "
                f"delta={report.drift.accuracy_delta:+.3f}"
            )
        if report.overall_calibration_error > 0.15:
            alerts.append(f"calibration_error_high: {report.overall_calibration_error:.3f}")
        if report.trend == "degrading":
            alerts.append("trend_degrading")
        return alerts
