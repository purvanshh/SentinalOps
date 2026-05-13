"""
TelemetryChaosEngine — Phase 48 operational chaos injection.

Accepts a list of raw event dicts and a CorruptionConfig, then returns
a corrupted list that models real-world telemetry failure modes.

Determinism guarantee:
  Given the same seed and config, output is always identical regardless
  of when or how many times the engine is called.

Pipeline (applied in order):
  1. Event loss      — randomly drop events per event_loss_rate
  2. Clock skew      — per-service timestamp drift via ClockSkewModel
  3. Delay injection — random forward-shift on selected events
  4. Severity corrupt— flip severity on selected events
  5. Payload corrupt — overwrite payload fields on selected events
  6. Stale replay    — backdate selected metric events
  7. Duplication     — duplicate selected events (inserted after original)
  8. Re-sort         — restore chronological order (after skew/delay)
"""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass
from typing import Any

from replay.chaos.clock_skew import ClockSkewModel
from replay.chaos.corruption_models import CorruptionConfig, CorruptionProfile
from replay.chaos.event_distortion import (
    apply_delay_to_dict,
    corrupt_payload,
    corrupt_severity,
    duplicate_event,
    make_stale,
)


@dataclass
class ChaosReport:
    """Summary of chaos mutations applied to a single event batch."""

    total_input: int
    total_output: int
    events_dropped: int
    events_duplicated: int
    events_delayed: int
    events_severity_corrupted: int
    events_payload_corrupted: int
    events_stale: int
    events_clock_skewed: int
    profile_used: str = ""

    @property
    def effective_loss_rate(self) -> float:
        if self.total_input == 0:
            return 0.0
        return round(self.events_dropped / self.total_input, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_input": self.total_input,
            "total_output": self.total_output,
            "events_dropped": self.events_dropped,
            "events_duplicated": self.events_duplicated,
            "events_delayed": self.events_delayed,
            "events_severity_corrupted": self.events_severity_corrupted,
            "events_payload_corrupted": self.events_payload_corrupted,
            "events_stale": self.events_stale,
            "events_clock_skewed": self.events_clock_skewed,
            "effective_loss_rate": self.effective_loss_rate,
            "profile_used": self.profile_used,
        }


class TelemetryChaosEngine:
    """
    Injects configurable operational chaos into a stream of telemetry events.

    Usage:
        engine = TelemetryChaosEngine(seed=42)
        corrupted, report = engine.inject(events, config)
    """

    def __init__(self, seed: int = 0) -> None:
        self._seed = seed

    def inject(
        self,
        events: list[dict[str, Any]],
        config: CorruptionConfig,
    ) -> tuple[list[dict[str, Any]], ChaosReport]:
        """
        Apply chaos mutations to events and return (corrupted_events, report).

        The RNG is re-seeded per call so output is deterministic per seed+config.
        """
        rng = random.Random(self._seed)
        skew_model = ClockSkewModel(
            max_skew_ms=config.clock_skew_ms,
            seed=self._seed + 1,
        )

        total_input = len(events)
        dropped = 0
        delayed = 0
        sev_corrupted = 0
        pay_corrupted = 0
        stale_count = 0
        clock_skewed = 0
        duplicates_added = 0

        result: list[dict[str, Any]] = []

        for ev in events:
            # 1. Event loss
            if config.event_loss_rate > 0 and rng.random() < config.event_loss_rate:
                dropped += 1
                continue

            ev_copy = copy.deepcopy(ev)

            # 2. Clock skew (per-service persistent offset)
            if config.clock_skew_ms > 0:
                ev_copy = skew_model.apply_to_event(ev_copy)
                clock_skewed += 1

            # 3. Delay injection
            if config.delay_probability > 0 and rng.random() < config.delay_probability:
                delay_s = rng.uniform(0.0, config.max_delay_seconds)
                ev_copy = apply_delay_to_dict(ev_copy, delay_s)
                delayed += 1

            # 4. Severity corruption
            if (
                config.severity_corruption_rate > 0
                and rng.random() < config.severity_corruption_rate
            ):
                ev_copy = corrupt_severity(ev_copy, rng)
                sev_corrupted += 1

            # 5. Payload corruption
            if config.payload_corruption_rate > 0 and rng.random() < config.payload_corruption_rate:
                ev_copy = corrupt_payload(ev_copy, rng)
                pay_corrupted += 1

            # 6. Stale replay (metric events only)
            if (
                config.stale_replay_rate > 0
                and ev_copy.get("kind") == "metric"
                and rng.random() < config.stale_replay_rate
            ):
                ev_copy = make_stale(ev_copy)
                stale_count += 1

            result.append(ev_copy)

            # 7. Duplication (inserted immediately after original)
            if config.duplication_rate > 0 and rng.random() < config.duplication_rate:
                dup = duplicate_event(ev_copy, rng)
                result.append(dup)
                duplicates_added += 1

        # 8. Re-sort chronologically (skew/delay can disorder events)
        result.sort(key=lambda e: e.get("timestamp_iso", ""))

        profile_name = config.profile.value if config.profile else ""
        report = ChaosReport(
            total_input=total_input,
            total_output=len(result),
            events_dropped=dropped,
            events_duplicated=duplicates_added,
            events_delayed=delayed,
            events_severity_corrupted=sev_corrupted,
            events_payload_corrupted=pay_corrupted,
            events_stale=stale_count,
            events_clock_skewed=clock_skewed,
            profile_used=profile_name,
        )
        return result, report

    def inject_profile(
        self,
        events: list[dict[str, Any]],
        profile: CorruptionProfile,
        overrides: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], ChaosReport]:
        """Convenience wrapper: build config from profile name then inject."""
        config = CorruptionConfig.from_profile(profile, overrides)
        return self.inject(events, config)
