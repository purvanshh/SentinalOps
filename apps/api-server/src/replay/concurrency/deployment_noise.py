"""
Deployment noise injection for Phase 48 operational chaos.

Real outages are surrounded by deployments — before, during, and after.
Many are unrelated to the incident but create false causal candidates.

Noise deployment types:
  HARMLESS_DURING_OUTAGE  — unrelated service deployed while incident is active
  UNRELATED_CONFIG_CHANGE — config update on a healthy service
  PARTIAL_ROLLOUT_FAILURE — canary deploy that partially failed (not root cause)
  POST_INCIDENT_DEPLOY    — deploy that arrived after incident onset
  FALSE_ROLLBACK          — rollback on unrelated service during incident
"""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass
from enum import Enum
from typing import Any


class NoiseDeploymentKind(str, Enum):
    HARMLESS_DURING_OUTAGE = "harmless_during_outage"
    UNRELATED_CONFIG_CHANGE = "unrelated_config_change"
    PARTIAL_ROLLOUT_FAILURE = "partial_rollout_failure"
    POST_INCIDENT_DEPLOY = "post_incident_deploy"
    FALSE_ROLLBACK = "false_rollback"


@dataclass
class NoiseDeployment:
    """A synthetic deployment event injected as noise."""

    event_id: str
    kind: str  # always "deployment"
    timestamp_iso: str
    service: str
    severity: str
    payload: dict[str, Any]
    noise_kind: NoiseDeploymentKind
    incident_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "kind": "deployment",
            "timestamp_iso": self.timestamp_iso,
            "service": self.service,
            "severity": self.severity,
            "payload": self.payload,
            "_noise_deployment": True,
            "_noise_kind": self.noise_kind.value,
            "incident_id": self.incident_id,
        }


_NOISE_SERVICES = [
    "billing-service",
    "analytics-pipeline",
    "email-notifier",
    "audit-logger",
    "report-generator",
    "background-worker",
]

_NOISE_PAYLOADS: dict[NoiseDeploymentKind, dict[str, Any]] = {
    NoiseDeploymentKind.HARMLESS_DURING_OUTAGE: {
        "version": "1.2.3",
        "deployer": "ci-bot",
        "description": "routine dependency update",
        "result": "success",
    },
    NoiseDeploymentKind.UNRELATED_CONFIG_CHANGE: {
        "change_type": "config",
        "key": "feature_flag_X",
        "old_value": "false",
        "new_value": "true",
        "deployer": "ops-team",
    },
    NoiseDeploymentKind.PARTIAL_ROLLOUT_FAILURE: {
        "version": "2.0.0-beta",
        "canary_percentage": 10,
        "result": "partial_failure",
        "failed_pods": 2,
        "total_pods": 20,
        "note": "canary failure on unrelated service",
    },
    NoiseDeploymentKind.POST_INCIDENT_DEPLOY: {
        "version": "1.5.1",
        "deployer": "ci-bot",
        "description": "scheduled post-freeze deploy",
        "result": "success",
    },
    NoiseDeploymentKind.FALSE_ROLLBACK: {
        "version": "1.4.9",
        "reason": "precautionary rollback",
        "deployer": "ops-team",
        "related_incident": None,
        "note": "unrelated service rollback coincided with incident",
    },
}


class NoiseDeploymentInjector:
    """
    Injects fake deployment events into an incident event stream.

    These deployments are NOT the root cause. They are operational noise that
    a root-cause system must not misattribute as the cause.
    """

    def __init__(self, seed: int = 0) -> None:
        self._rng = random.Random(seed)

    def inject(
        self,
        events: list[dict[str, Any]],
        noise_count: int = 3,
        kinds: list[NoiseDeploymentKind] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Insert `noise_count` fake deployments into the event stream.

        Returns a new sorted list with noise events interleaved.
        """
        if not events:
            return []

        available_kinds = kinds or list(NoiseDeploymentKind)
        timestamps = [e.get("timestamp_iso", "") for e in events if e.get("timestamp_iso")]
        if not timestamps:
            return list(events)

        t_min = min(timestamps)
        t_max = max(timestamps)

        result = list(copy.deepcopy(events))
        for _ in range(noise_count):
            kind = self._rng.choice(available_kinds)
            noise_ts = self._random_timestamp_between(t_min, t_max)
            service = self._rng.choice(_NOISE_SERVICES)
            payload = dict(_NOISE_PAYLOADS[kind])
            payload["service"] = service

            nd = NoiseDeployment(
                event_id=f"noise_deploy_{self._rng.randint(0, 0xFFFFFFFF):08x}",
                kind="deployment",
                timestamp_iso=noise_ts,
                service=service,
                severity="info",
                payload=payload,
                noise_kind=kind,
            )
            result.append(nd.to_dict())

        result.sort(key=lambda e: e.get("timestamp_iso", ""))
        return result

    def _random_timestamp_between(self, t_min: str, t_max: str) -> str:
        """Pick a random ISO timestamp in [t_min, t_max]."""
        # Treat as strings — works because ISO 8601 sorts lexicographically
        if t_min >= t_max:
            return t_min
        # Fall back: just return t_min + small delta via ordinal trick
        try:
            from datetime import datetime, timedelta

            def _p(s: str) -> datetime:
                return datetime.fromisoformat(s.replace("Z", "+00:00"))

            dt_min = _p(t_min)
            dt_max = _p(t_max)
            span_s = (dt_max - dt_min).total_seconds()
            offset_s = self._rng.uniform(0, span_s)
            dt = dt_min + timedelta(seconds=offset_s)
            return dt.strftime("%Y-%m-%dT%H:%M:%S") + "Z"
        except Exception:
            return t_min
