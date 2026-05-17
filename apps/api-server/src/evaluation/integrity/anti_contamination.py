"""Anti-contamination guard — prevents golden labels from entering evaluation predictions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


_CONTAMINATION_FIELD_PATTERNS = [
    "golden_label",
    "true_label",
    "ground_truth",
    "root_cause",  # must not be passed to scorer as input
    "_label",
    "correct_answer",
    "expected_output",
    "_golden",
    "_contamination",
]


@dataclass
class ContaminationReport:
    clean: bool
    contaminated_fields: list[str]
    contamination_rate: float
    samples_checked: int
    samples_contaminated: int
    severity: str
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "clean": self.clean,
            "contaminated_fields": self.contaminated_fields,
            "contamination_rate": self.contamination_rate,
            "samples_checked": self.samples_checked,
            "samples_contaminated": self.samples_contaminated,
            "severity": self.severity,
            "recommendation": self.recommendation,
        }


class AntiContaminationGuard:
    """Block golden label fields from reaching the scorer.

    Contamination means a scorer receives the correct answer as one of its
    inputs, making evaluation metrics meaningless.

    This guard enforces a hard boundary between:
    - Evaluation input (incident data without labels)
    - Golden data (labels used only for post-hoc comparison)
    """

    def scrub(self, sample: dict[str, Any]) -> dict[str, Any]:
        """Return a copy of sample with all contamination fields removed."""
        return {k: v for k, v in sample.items() if not self._is_contamination_field(k)}

    def scrub_batch(self, samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.scrub(s) for s in samples]

    def check(self, samples: list[dict[str, Any]]) -> ContaminationReport:
        contaminated_fields: set[str] = set()
        samples_contaminated = 0

        for sample in samples:
            fields_in_sample = [k for k in sample if self._is_contamination_field(k)]
            if fields_in_sample:
                samples_contaminated += 1
                contaminated_fields.update(fields_in_sample)

        rate = round(samples_contaminated / len(samples), 4) if samples else 0.0
        clean = samples_contaminated == 0

        if clean:
            severity = "none"
            recommendation = "No contamination detected."
        elif rate < 0.10:
            severity = "low"
            recommendation = "Minor contamination. Scrub fields before evaluation."
        elif rate < 0.50:
            severity = "medium"
            recommendation = "Significant contamination. Evaluation results are unreliable — re-run after scrubbing."
        else:
            severity = "critical"
            recommendation = "Pervasive contamination. All benchmark results from this dataset are invalid."

        return ContaminationReport(
            clean=clean,
            contaminated_fields=sorted(contaminated_fields),
            contamination_rate=rate,
            samples_checked=len(samples),
            samples_contaminated=samples_contaminated,
            severity=severity,
            recommendation=recommendation,
        )

    def assert_clean(self, samples: list[dict[str, Any]]) -> None:
        """Raise if any contamination is detected — use as a hard gate before scoring."""
        report = self.check(samples)
        if not report.clean:
            raise ContaminationError(
                f"Contamination detected in {report.samples_contaminated}/{report.samples_checked} samples. "
                f"Fields: {report.contaminated_fields}. "
                f"Recommendation: {report.recommendation}"
            )

    def _is_contamination_field(self, field_name: str) -> bool:
        lower = field_name.lower()
        return any(pattern in lower for pattern in _CONTAMINATION_FIELD_PATTERNS)


class ContaminationError(Exception):
    """Raised when golden label contamination is detected in evaluation inputs."""
