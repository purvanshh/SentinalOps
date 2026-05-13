"""
Event distortion functions for telemetry chaos injection.

Each distortion is a pure function operating on a single event dict.
Mutations are applied to copies; originals are never modified.

Distortion catalogue:
  corrupt_severity    — flip severity to a wrong level
  corrupt_payload     — overwrite payload fields with noise
  make_stale          — backdate a metric to simulate stale replay
  duplicate_event     — produce a near-identical copy with shifted timestamp
  inject_missing_field — remove a key field from the payload
"""

from __future__ import annotations

import copy
import random
import uuid
from datetime import datetime, timedelta

_SEVERITY_LEVELS = ["info", "warning", "error", "critical"]

_STALE_BACKDATE_SECONDS = 300  # 5 minutes


def _parse_ts(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _to_iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + "Z"


def corrupt_severity(event: dict, rng: random.Random) -> dict:
    """Replace the event severity with a randomly chosen different level."""
    ev = copy.deepcopy(event)
    current = ev.get("severity", "info")
    candidates = [s for s in _SEVERITY_LEVELS if s != current]
    ev["severity"] = rng.choice(candidates)
    ev["_severity_corrupted"] = True
    return ev


def corrupt_payload(event: dict, rng: random.Random, fields_to_corrupt: int = 1) -> dict:
    """
    Overwrite a random subset of payload fields with placeholder noise.

    If the payload is empty or has no corruptible fields, adds a noise key.
    """
    ev = copy.deepcopy(event)
    payload = ev.get("payload", {})
    if isinstance(payload, dict) and payload:
        keys = list(payload.keys())
        for k in rng.sample(keys, min(fields_to_corrupt, len(keys))):
            payload[k] = f"<corrupted:{rng.randint(1000, 9999)}>"
    else:
        ev["payload"] = {"_noise": f"corrupted:{rng.randint(1000, 9999)}"}
    ev["payload"] = payload
    ev["_payload_corrupted"] = True
    return ev


def make_stale(event: dict, backdate_seconds: int = _STALE_BACKDATE_SECONDS) -> dict:
    """
    Backdate an event to simulate stale telemetry replay.

    Stale metrics look healthy because they reflect an earlier, stable state.
    """
    ev = copy.deepcopy(event)
    ts = ev.get("timestamp_iso", "")
    dt = _parse_ts(ts)
    if dt is not None:
        stale_dt = dt - timedelta(seconds=backdate_seconds)
        ev["timestamp_iso"] = _to_iso(stale_dt)
    ev["_stale_replay"] = True
    return ev


def duplicate_event(event: dict, rng: random.Random, jitter_seconds: float = 2.0) -> dict:
    """
    Produce a near-identical copy with a new event_id and a small timestamp jitter.

    Models alert storms, flapping sensors, and double-published telemetry.
    """
    ev = copy.deepcopy(event)
    ev["event_id"] = f"{event.get('event_id', 'dup')}__dup_{uuid.uuid4().hex[:6]}"
    ts = ev.get("timestamp_iso", "")
    dt = _parse_ts(ts)
    if dt is not None:
        jitter = rng.uniform(-jitter_seconds, jitter_seconds)
        ev["timestamp_iso"] = _to_iso(dt + timedelta(seconds=jitter))
    ev["_duplicate"] = True
    return ev


def inject_missing_field(event: dict, rng: random.Random) -> dict:
    """
    Remove a randomly chosen non-critical field to simulate incomplete telemetry.

    Fields 'event_id' and 'kind' are never removed (they break parsing).
    """
    ev = copy.deepcopy(event)
    removable = [k for k in ev if k not in ("event_id", "kind", "_duplicate", "_stale_replay")]
    if removable:
        field = rng.choice(removable)
        del ev[field]
        ev["_missing_field"] = field
    return ev


def apply_delay_to_dict(event: dict, delay_seconds: float) -> dict:
    """
    Forward-shift a timestamp to simulate delayed event delivery.

    Does not modify event_id or any payload fields.
    """
    ev = copy.deepcopy(event)
    ts = ev.get("timestamp_iso", "")
    dt = _parse_ts(ts)
    if dt is not None and delay_seconds > 0:
        ev["timestamp_iso"] = _to_iso(dt + timedelta(seconds=delay_seconds))
        ev["_delayed_seconds"] = round(delay_seconds, 2)
    return ev
