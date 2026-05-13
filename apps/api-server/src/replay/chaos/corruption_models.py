"""
Corruption profiles and configuration models for telemetry chaos injection.

Each CorruptionProfile represents a class of real-world telemetry failure:
  NETWORK_PARTITION  — packets dropped, high loss, delayed delivery
  TELEMETRY_BLACKOUT — instrumentation dead for a window
  ALERT_STORM        — alerts duplicated and severity inflated
  CLOCK_DRIFT        — timestamps skewed across services
  CACHE_STALE        — metrics frozen at last-known values
  PARTIAL_DEPLOYMENT — deploys partially rolled out, mixed signals
  SPLIT_BRAIN        — two independent views of the same incident
  METRIC_FREEZE      — metric stream stops updating (looks healthy but isn't)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CorruptionProfile(str, Enum):
    NETWORK_PARTITION = "network_partition"
    TELEMETRY_BLACKOUT = "telemetry_blackout"
    ALERT_STORM = "alert_storm"
    CLOCK_DRIFT = "clock_drift"
    CACHE_STALE = "cache_stale"
    PARTIAL_DEPLOYMENT = "partial_deployment"
    SPLIT_BRAIN = "split_brain"
    METRIC_FREEZE = "metric_freeze"


# Preset parameter tuples for each profile: (loss_rate, duplication_rate, skew_ms, delay_p)
_PROFILE_DEFAULTS: dict[CorruptionProfile, dict[str, Any]] = {
    CorruptionProfile.NETWORK_PARTITION: {
        "event_loss_rate": 0.40,
        "duplication_rate": 0.05,
        "clock_skew_ms": 500,
        "delay_probability": 0.30,
        "severity_corruption_rate": 0.0,
        "payload_corruption_rate": 0.05,
    },
    CorruptionProfile.TELEMETRY_BLACKOUT: {
        "event_loss_rate": 0.70,
        "duplication_rate": 0.0,
        "clock_skew_ms": 0,
        "delay_probability": 0.0,
        "severity_corruption_rate": 0.0,
        "payload_corruption_rate": 0.0,
    },
    CorruptionProfile.ALERT_STORM: {
        "event_loss_rate": 0.0,
        "duplication_rate": 0.50,
        "clock_skew_ms": 50,
        "delay_probability": 0.10,
        "severity_corruption_rate": 0.20,
        "payload_corruption_rate": 0.0,
    },
    CorruptionProfile.CLOCK_DRIFT: {
        "event_loss_rate": 0.0,
        "duplication_rate": 0.0,
        "clock_skew_ms": 30_000,
        "delay_probability": 0.0,
        "severity_corruption_rate": 0.0,
        "payload_corruption_rate": 0.0,
    },
    CorruptionProfile.CACHE_STALE: {
        "event_loss_rate": 0.10,
        "duplication_rate": 0.0,
        "clock_skew_ms": 0,
        "delay_probability": 0.0,
        "severity_corruption_rate": 0.0,
        "payload_corruption_rate": 0.30,
        "stale_replay_rate": 0.30,
    },
    CorruptionProfile.PARTIAL_DEPLOYMENT: {
        "event_loss_rate": 0.20,
        "duplication_rate": 0.10,
        "clock_skew_ms": 200,
        "delay_probability": 0.20,
        "severity_corruption_rate": 0.10,
        "payload_corruption_rate": 0.10,
    },
    CorruptionProfile.SPLIT_BRAIN: {
        "event_loss_rate": 0.0,
        "duplication_rate": 0.30,
        "clock_skew_ms": 10_000,
        "delay_probability": 0.0,
        "severity_corruption_rate": 0.15,
        "payload_corruption_rate": 0.15,
    },
    CorruptionProfile.METRIC_FREEZE: {
        "event_loss_rate": 0.60,
        "duplication_rate": 0.0,
        "clock_skew_ms": 0,
        "delay_probability": 0.0,
        "severity_corruption_rate": 0.0,
        "payload_corruption_rate": 0.0,
        "stale_replay_rate": 0.50,
    },
}


@dataclass
class CorruptionConfig:
    """
    Parameterises chaos injection for a single replay pass.

    All probability fields are in [0.0, 1.0].
    clock_skew_ms is the maximum millisecond deviation applied to timestamps.
    max_delay_seconds is the upper bound for event delay injection.
    """

    profile: CorruptionProfile | None = None

    # Per-event probabilities
    corruption_probability: float = 0.0
    event_loss_rate: float = 0.0
    duplication_rate: float = 0.05
    delay_probability: float = 0.10
    severity_corruption_rate: float = 0.0
    payload_corruption_rate: float = 0.0
    stale_replay_rate: float = 0.0

    # Delay / skew magnitudes
    clock_skew_ms: int = 0
    max_delay_seconds: float = 30.0

    # Optional override dict (merged over profile defaults)
    overrides: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_profile(
        cls,
        profile: CorruptionProfile,
        overrides: dict[str, Any] | None = None,
    ) -> "CorruptionConfig":
        """Build a CorruptionConfig from a named profile, optionally overriding fields."""
        defaults = dict(_PROFILE_DEFAULTS[profile])
        if overrides:
            defaults.update(overrides)
        return cls(
            profile=profile,
            corruption_probability=defaults.get(
                "corruption_probability",
                defaults.get("event_loss_rate", 0.0),
            ),
            event_loss_rate=float(defaults.get("event_loss_rate", 0.0)),
            duplication_rate=float(defaults.get("duplication_rate", 0.0)),
            delay_probability=float(defaults.get("delay_probability", 0.0)),
            severity_corruption_rate=float(defaults.get("severity_corruption_rate", 0.0)),
            payload_corruption_rate=float(defaults.get("payload_corruption_rate", 0.0)),
            stale_replay_rate=float(defaults.get("stale_replay_rate", 0.0)),
            clock_skew_ms=int(defaults.get("clock_skew_ms", 0)),
            max_delay_seconds=float(defaults.get("max_delay_seconds", 30.0)),
            overrides=overrides or {},
        )

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CorruptionConfig":
        """Build a CorruptionConfig from an arbitrary dict."""
        profile_name = d.get("profile")
        profile = CorruptionProfile(profile_name) if profile_name else None
        return cls(
            profile=profile,
            corruption_probability=float(d.get("corruption_probability", 0.0)),
            event_loss_rate=float(d.get("event_loss_rate", 0.0)),
            duplication_rate=float(d.get("duplication_rate", 0.0)),
            delay_probability=float(d.get("delay_probability", 0.0)),
            severity_corruption_rate=float(d.get("severity_corruption_rate", 0.0)),
            payload_corruption_rate=float(d.get("payload_corruption_rate", 0.0)),
            stale_replay_rate=float(d.get("stale_replay_rate", 0.0)),
            clock_skew_ms=int(d.get("clock_skew_ms", 0)),
            max_delay_seconds=float(d.get("max_delay_seconds", 30.0)),
        )
