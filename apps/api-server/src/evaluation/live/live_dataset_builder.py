"""
Live dataset builder for SentinelOps Phase 47.

Assembles evaluation datasets from replay sessions and telemetry snapshots.
Supports filtering, stratification, and reproducible dataset versioning.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class EvaluationSample:
    """One ground-truth evaluation sample derived from a replay session."""

    sample_id: str
    incident_id: str
    service: str
    severity: str
    timestamp_iso: str
    event_count: int
    telemetry_completeness: float
    ground_truth_root_cause: str
    ground_truth_resolution: str
    labels: dict[str, str] = field(default_factory=dict)
    source_session_hash: str = ""

    def fingerprint(self) -> str:
        blob = f"{self.sample_id}:{self.incident_id}:{self.timestamp_iso}"
        return hashlib.sha256(blob.encode()).hexdigest()[:16]


@dataclass
class EvaluationDataset:
    """A versioned collection of evaluation samples."""

    dataset_id: str
    version: str
    created_at: str
    samples: list[EvaluationSample] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def size(self) -> int:
        return len(self.samples)

    @property
    def service_distribution(self) -> dict[str, int]:
        dist: dict[str, int] = {}
        for s in self.samples:
            dist[s.service] = dist.get(s.service, 0) + 1
        return dist

    @property
    def severity_distribution(self) -> dict[str, int]:
        dist: dict[str, int] = {}
        for s in self.samples:
            dist[s.severity] = dist.get(s.severity, 0) + 1
        return dist

    @property
    def mean_completeness(self) -> float:
        if not self.samples:
            return 0.0
        return sum(s.telemetry_completeness for s in self.samples) / len(self.samples)

    def dataset_hash(self) -> str:
        fps = "|".join(s.fingerprint() for s in sorted(self.samples, key=lambda x: x.sample_id))
        return hashlib.sha256(fps.encode()).hexdigest()[:24]

    def filter_by_severity(self, severity: str) -> "EvaluationDataset":
        filtered = [s for s in self.samples if s.severity == severity]
        return EvaluationDataset(
            dataset_id=f"{self.dataset_id}__{severity}",
            version=self.version,
            created_at=self.created_at,
            samples=filtered,
            metadata={**self.metadata, "filtered_by_severity": severity},
        )

    def filter_by_service(self, service: str) -> "EvaluationDataset":
        filtered = [s for s in self.samples if s.service == service]
        return EvaluationDataset(
            dataset_id=f"{self.dataset_id}__{service}",
            version=self.version,
            created_at=self.created_at,
            samples=filtered,
            metadata={**self.metadata, "filtered_by_service": service},
        )


class LiveDatasetBuilder:
    """Builds versioned evaluation datasets from replay sessions and raw telemetry."""

    def __init__(self, dataset_id: str = "live", version: str = "1.0") -> None:
        self._dataset_id = dataset_id
        self._version = version
        self._samples: list[EvaluationSample] = []

    def ingest_replay_incident(
        self,
        incident_id: str,
        events: list[dict[str, Any]],
        ground_truth_root_cause: str,
        ground_truth_resolution: str,
        session_hash: str = "",
    ) -> EvaluationSample:
        """Create a sample from a replay incident's events."""
        service = self._dominant_service(events)
        severity = self._dominant_severity(events)
        timestamp_iso = self._earliest_timestamp(events)
        completeness = self._compute_completeness(events)
        sample_id = f"{incident_id}_{len(self._samples):04d}"

        sample = EvaluationSample(
            sample_id=sample_id,
            incident_id=incident_id,
            service=service,
            severity=severity,
            timestamp_iso=timestamp_iso,
            event_count=len(events),
            telemetry_completeness=completeness,
            ground_truth_root_cause=ground_truth_root_cause,
            ground_truth_resolution=ground_truth_resolution,
            labels=self._extract_labels(events),
            source_session_hash=session_hash,
        )
        self._samples.append(sample)
        return sample

    def ingest_raw_sample(self, sample: EvaluationSample) -> None:
        self._samples.append(sample)

    def build(self) -> EvaluationDataset:
        return EvaluationDataset(
            dataset_id=self._dataset_id,
            version=self._version,
            created_at=datetime.now(timezone.utc).isoformat(),
            samples=list(self._samples),
            metadata={"builder": "LiveDatasetBuilder", "total_samples": len(self._samples)},
        )

    def reset(self) -> None:
        self._samples.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _dominant_service(self, events: list[dict[str, Any]]) -> str:
        counts: dict[str, int] = {}
        for ev in events:
            svc = ev.get("service", "unknown")
            if svc:
                counts[svc] = counts.get(svc, 0) + 1
        return max(counts, key=lambda k: counts[k]) if counts else "unknown"

    def _dominant_severity(self, events: list[dict[str, Any]]) -> str:
        rank = {"critical": 4, "error": 3, "warning": 2, "info": 1, "debug": 0}
        best = "info"
        for ev in events:
            sev = ev.get("severity", "info")
            if rank.get(sev, 0) > rank.get(best, 0):
                best = sev
        return best

    def _earliest_timestamp(self, events: list[dict[str, Any]]) -> str:
        ts_list = [
            ev.get("timestamp_iso", "") or ev.get("timestamp", "")
            for ev in events
            if ev.get("timestamp_iso") or ev.get("timestamp")
        ]
        return min(ts_list) if ts_list else ""

    def _compute_completeness(self, events: list[dict[str, Any]]) -> float:
        expected = {"metric", "log", "alert"}
        present = {ev.get("kind", "").lower() for ev in events}
        matched = expected & present
        return len(matched) / len(expected)

    def _extract_labels(self, events: list[dict[str, Any]]) -> dict[str, str]:
        merged: dict[str, str] = {}
        for ev in events:
            labels = ev.get("labels", {})
            if isinstance(labels, dict):
                for k, v in labels.items():
                    if k not in merged:
                        merged[str(k)] = str(v)
        return merged


def build_dataset_from_json(
    path: str,
    dataset_id: str = "live",
    version: str = "1.0",
) -> EvaluationDataset:
    """Load a JSON file of labeled incidents and build an EvaluationDataset."""
    with open(path) as fh:
        records = json.load(fh)

    builder = LiveDatasetBuilder(dataset_id=dataset_id, version=version)
    for record in records:
        incident_id = record.get("incident_id", "unknown")
        events = record.get("events", [])
        root_cause = record.get("ground_truth_root_cause", "")
        resolution = record.get("ground_truth_resolution", "")
        session_hash = record.get("session_hash", "")
        builder.ingest_replay_incident(
            incident_id=incident_id,
            events=events,
            ground_truth_root_cause=root_cause,
            ground_truth_resolution=resolution,
            session_hash=session_hash,
        )
    return builder.build()
