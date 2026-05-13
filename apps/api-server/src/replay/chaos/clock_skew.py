"""
Clock skew injection for telemetry chaos simulation.

Real distributed systems have clock drift between nodes. This module
applies deterministic, seeded skew to event timestamps to simulate:
  - NTP sync failures
  - Container clock drift
  - Cross-region timestamp mismatches
  - Retroactively-stamped telemetry
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any


def _parse_ts(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _to_iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + "Z"


def apply_clock_skew(
    timestamp_iso: str,
    max_skew_ms: int,
    rng: random.Random,
    direction: str = "both",
) -> str:
    """
    Apply a random clock skew to a single ISO timestamp.

    direction: "forward" | "backward" | "both"
    Returns the original string on parse failure.
    """
    if max_skew_ms <= 0:
        return timestamp_iso

    dt = _parse_ts(timestamp_iso)
    if dt is None:
        return timestamp_iso

    skew_ms = rng.randint(0, max_skew_ms)
    if direction == "forward":
        delta_ms = skew_ms
    elif direction == "backward":
        delta_ms = -skew_ms
    else:
        delta_ms = skew_ms if rng.random() < 0.5 else -skew_ms

    skewed = dt + timedelta(milliseconds=delta_ms)
    return _to_iso(skewed)


def apply_delay(
    timestamp_iso: str,
    max_delay_seconds: float,
    rng: random.Random,
) -> str:
    """Delay an event by a random amount (forward-only)."""
    if max_delay_seconds <= 0:
        return timestamp_iso

    dt = _parse_ts(timestamp_iso)
    if dt is None:
        return timestamp_iso

    delay_s = rng.uniform(0, max_delay_seconds)
    delayed = dt + timedelta(seconds=delay_s)
    return _to_iso(delayed)


class ClockSkewModel:
    """
    Tracks per-service clock skew offsets for consistent multi-event skew.

    Each service gets one skew offset assigned on first reference; subsequent
    events from the same service receive the same offset. This models a single
    node with a drifted clock, not per-event random skew.
    """

    def __init__(self, max_skew_ms: int, seed: int = 0) -> None:
        self._max_skew_ms = max_skew_ms
        self._rng = random.Random(seed)
        self._offsets: dict[str, int] = {}

    def skew_for_service(self, service: str) -> int:
        """Return (and persist) the skew offset in ms for a service."""
        if service not in self._offsets:
            skew = self._rng.randint(-self._max_skew_ms, self._max_skew_ms)
            self._offsets[service] = skew
        return self._offsets[service]

    def apply(self, timestamp_iso: str, service: str) -> str:
        """Apply the service's persistent clock skew to a timestamp."""
        offset_ms = self.skew_for_service(service)
        if offset_ms == 0:
            return timestamp_iso

        dt = _parse_ts(timestamp_iso)
        if dt is None:
            return timestamp_iso

        skewed = dt + timedelta(milliseconds=offset_ms)
        return _to_iso(skewed)

    def offsets(self) -> dict[str, int]:
        return dict(self._offsets)

    def apply_to_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """Return a copy of the event dict with timestamp_iso skewed."""
        ev = dict(event)
        service = ev.get("service", "unknown")
        ts = ev.get("timestamp_iso", "")
        ev["timestamp_iso"] = self.apply(ts, service)
        ev["_clock_skew_applied_ms"] = self.skew_for_service(service)
        return ev
