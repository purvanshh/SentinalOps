"""
Telemetry Normalizer for SentinelOps Phase 47.

Converts heterogeneous telemetry from multiple sources into a unified
UnifiedTelemetryEvent schema. Handles:
  - timestamp normalization to UTC ISO-8601
  - severity normalization to: critical/error/warning/info/debug
  - service name normalization (strip prefixes, lowercase)
  - deployment identifier extraction
  - label canonicalization
  - topology-aware enrichment (upstream/downstream services)
  - ingestion confidence scoring

Partial telemetry is accepted: missing fields get neutral defaults.
Malformed events are quarantined with a reason rather than dropped.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

_SEVERITY_MAP: dict[str, str] = {
    "critical": "critical",
    "crit": "critical",
    "fatal": "critical",
    "alert": "critical",
    "emerg": "critical",
    "error": "error",
    "err": "error",
    "warning": "warning",
    "warn": "warning",
    "notice": "info",
    "info": "info",
    "informational": "info",
    "debug": "debug",
    "trace": "debug",
    "unknown": "info",
    "": "info",
}


@dataclass
class UnifiedTelemetryEvent:
    """Normalized telemetry event from any source."""

    event_id: str
    source_kind: str  # "prometheus", "loki", "github", "kubernetes", "unknown"
    timestamp_iso: str
    service: str
    severity: str
    message: str
    labels: dict[str, str]
    raw_payload: dict[str, Any]
    upstream_services: list[str]
    downstream_services: list[str]
    dependency_count: int
    deployment_id: str
    incident_id: str | None
    ingestion_confidence: float  # 0.0 = very uncertain, 1.0 = fully complete

    def fingerprint(self) -> str:
        canonical = json.dumps(
            {
                "event_id": self.event_id,
                "source_kind": self.source_kind,
                "timestamp_iso": self.timestamp_iso,
                "service": self.service,
            },
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "source_kind": self.source_kind,
            "timestamp_iso": self.timestamp_iso,
            "service": self.service,
            "severity": self.severity,
            "message": self.message,
            "labels": self.labels,
            "upstream_services": self.upstream_services,
            "downstream_services": self.downstream_services,
            "dependency_count": self.dependency_count,
            "deployment_id": self.deployment_id,
            "incident_id": self.incident_id,
            "ingestion_confidence": round(self.ingestion_confidence, 4),
            "fingerprint": self.fingerprint(),
        }


@dataclass
class QuarantinedEvent:
    """A telemetry event that could not be normalized."""

    raw: dict[str, Any]
    reason: str
    source_kind: str


@dataclass
class NormalizationResult:
    """Result of normalizing a batch of telemetry events."""

    events: list[UnifiedTelemetryEvent]
    quarantined: list[QuarantinedEvent]
    source_kind: str

    @property
    def total_attempted(self) -> int:
        return len(self.events) + len(self.quarantined)

    @property
    def success_rate(self) -> float:
        if self.total_attempted == 0:
            return 1.0
        return round(len(self.events) / self.total_attempted, 4)

    @property
    def mean_confidence(self) -> float:
        if not self.events:
            return 0.0
        return round(sum(ev.ingestion_confidence for ev in self.events) / len(self.events), 4)


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------


def normalize_severity(raw: str) -> str:
    return _SEVERITY_MAP.get(str(raw).lower().strip(), "info")


def normalize_timestamp(raw: Any) -> str:
    """Normalize a timestamp to UTC ISO-8601. Returns '' on failure."""
    if not raw:
        return ""
    if isinstance(raw, (int, float)):
        try:
            # Unix epoch seconds
            dt = datetime.fromtimestamp(raw, tz=timezone.utc)
            return dt.isoformat()
        except (OSError, OverflowError, ValueError):
            pass
    if isinstance(raw, str):
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S+00:00",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                dt = datetime.strptime(raw, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.isoformat()
            except ValueError:
                continue
        # Already ISO: try fromisoformat
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return dt.isoformat()
        except ValueError:
            pass
    return str(raw)


def normalize_service(raw: str) -> str:
    """Normalize service name: lowercase, strip common k8s prefixes."""
    name = str(raw).strip().lower()
    for prefix in ("deployment/", "service/", "pod/", "daemonset/", "statefulset/"):
        if name.startswith(prefix):
            name = name[len(prefix) :]
            break
    return name


def _ingestion_confidence(
    has_timestamp: bool,
    has_service: bool,
    has_severity: bool,
    has_message: bool,
    has_labels: bool,
) -> float:
    """Score completeness of an ingested event."""
    score = 0.0
    if has_timestamp:
        score += 0.30
    if has_service:
        score += 0.25
    if has_severity:
        score += 0.15
    if has_message:
        score += 0.20
    if has_labels:
        score += 0.10
    return round(score, 4)


class TelemetryNormalizer:
    """
    Normalizes heterogeneous telemetry into UnifiedTelemetryEvents.

    Accepts a topology_map to enrich events with upstream/downstream services.
    """

    def __init__(self, topology_map: dict[str, list[str]] | None = None) -> None:
        # topology_map: service → list of downstream services
        self._topology: dict[str, list[str]] = topology_map or {}
        self._upstream_index: dict[str, list[str]] = {}
        self._build_upstream_index()

    def _build_upstream_index(self) -> None:
        for svc, downstreams in self._topology.items():
            for ds in downstreams:
                self._upstream_index.setdefault(ds, []).append(svc)

    def normalize(
        self, raw: dict[str, Any], source_kind: str = "unknown"
    ) -> UnifiedTelemetryEvent | QuarantinedEvent:
        """Normalize a single raw event."""
        try:
            raw_ts = raw.get("timestamp_iso") or raw.get("timestamp") or raw.get("time", "")
            ts = normalize_timestamp(raw_ts)

            raw_svc = str(raw.get("service") or raw.get("labels", {}).get("service", "") or "")
            service = normalize_service(raw_svc)

            severity = normalize_severity(
                str(raw.get("severity") or raw.get("level") or raw.get("status", ""))
            )
            message = str(raw.get("message") or raw.get("description") or raw.get("text", ""))
            labels = {str(k): str(v) for k, v in raw.get("labels", {}).items()}

            event_id = str(raw.get("event_id") or raw.get("id") or f"norm_{abs(hash(str(raw)))}")
            deployment_id = str(
                raw.get("deployment_id")
                or labels.get("deployment_id")
                or labels.get("deploy_id", "")
            )
            incident_id = raw.get("incident_id")

            downstream = self._topology.get(service, [])
            upstream = self._upstream_index.get(service, [])
            dep_count = len(downstream) + len(upstream)

            confidence = _ingestion_confidence(
                has_timestamp=bool(ts),
                has_service=bool(service),
                has_severity=bool(raw.get("severity") or raw.get("level")),
                has_message=bool(message),
                has_labels=bool(labels),
            )

            return UnifiedTelemetryEvent(
                event_id=event_id,
                source_kind=source_kind,
                timestamp_iso=ts,
                service=service,
                severity=severity,
                message=message,
                labels=labels,
                raw_payload=raw,
                upstream_services=upstream,
                downstream_services=downstream,
                dependency_count=dep_count,
                deployment_id=deployment_id,
                incident_id=incident_id,
                ingestion_confidence=confidence,
            )
        except Exception as exc:
            return QuarantinedEvent(raw=raw, reason=str(exc), source_kind=source_kind)

    def normalize_batch(
        self, batch: list[dict[str, Any]], source_kind: str = "unknown"
    ) -> NormalizationResult:
        events: list[UnifiedTelemetryEvent] = []
        quarantined: list[QuarantinedEvent] = []
        for raw in batch:
            result = self.normalize(raw, source_kind=source_kind)
            if isinstance(result, UnifiedTelemetryEvent):
                events.append(result)
            else:
                quarantined.append(result)
        return NormalizationResult(events=events, quarantined=quarantined, source_kind=source_kind)
