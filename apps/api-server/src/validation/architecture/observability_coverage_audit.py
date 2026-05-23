"""Observability coverage audit — checks which modules lack instrumentation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

_OBSERVABILITY_MARKERS = [
    "logger",
    "logging",
    "metrics",
    "prometheus",
    "trace",
    "span",
    "structlog",
    "sentry",
]

_SKIP_LAYERS = {"tests", "__pycache__", "migrations", "seed"}


@dataclass
class CoverageReport:
    total_modules: int
    instrumented_modules: int
    uninstrumented_modules: list[str]
    coverage_rate: float
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_modules": self.total_modules,
            "instrumented_modules": self.instrumented_modules,
            "uninstrumented_modules": self.uninstrumented_modules,
            "coverage_rate": self.coverage_rate,
            "recommendation": self.recommendation,
        }


class ObservabilityCoverageAuditor:
    """Audit which source modules contain at least one observability call.

    A module with no logging, metrics, or tracing is invisible in production.
    This auditor identifies those blind spots without prescribing a fix.
    """

    def audit(self, src_root: Path) -> CoverageReport:
        all_modules: list[str] = []
        instrumented: list[str] = []

        for py_file in src_root.rglob("*.py"):
            parts = py_file.parts
            if any(skip in parts for skip in _SKIP_LAYERS):
                continue
            if py_file.name.startswith("test_") or py_file.name == "conftest.py":
                continue

            rel = str(py_file.relative_to(src_root))
            all_modules.append(rel)
            if self._is_instrumented(py_file):
                instrumented.append(rel)

        uninstrumented = [m for m in all_modules if m not in instrumented]
        total = len(all_modules)
        rate = round(len(instrumented) / total, 4) if total else 0.0

        return CoverageReport(
            total_modules=total,
            instrumented_modules=len(instrumented),
            uninstrumented_modules=uninstrumented,
            coverage_rate=rate,
            recommendation=self._recommendation(rate, uninstrumented),
        )

    def _is_instrumented(self, path: Path) -> bool:
        try:
            source = path.read_text(encoding="utf-8").lower()
            return any(marker in source for marker in _OBSERVABILITY_MARKERS)
        except Exception:
            return False

    def _recommendation(self, rate: float, uninstrumented: list[str]) -> str:
        if rate >= 0.80:
            return (
                f"Good observability coverage ({rate:.0%}). "
                f"{len(uninstrumented)} modules lack instrumentation."
            )
        if rate >= 0.50:
            return (
                f"Moderate coverage ({rate:.0%}). Priority: add logging to "
                f"{', '.join(uninstrumented[:5])}{'...' if len(uninstrumented) > 5 else ''}."
            )
        return (
            f"Low observability coverage ({rate:.0%}). Most modules lack instrumentation "
            "— significant blind spot in production."
        )
