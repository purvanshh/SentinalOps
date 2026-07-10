from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        val_str = str(value)
        return datetime.fromisoformat(val_str.replace("Z", "+00:00"))
    except ValueError:
        if isinstance(value, str) and re.match(r"^\d{2}:\d{2}:\d{2}$", value):
            return datetime.fromisoformat(f"2026-05-13T{value}+00:00")
        return None


def compute_evidence_hash(item: dict[str, Any]) -> str:
    # Serialize to JSON with sorted keys for determinism
    serialized = json.dumps(item, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def weight_evidence(evidence_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # 1. Parse timestamps to find the most recent event
    parsed_timestamps = []
    for item in evidence_items:
        ts = _parse_timestamp(item.get("timestamp"))
        if ts:
            # Ensure timezone-aware comparison
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            parsed_timestamps.append(ts)

    max_ts = max(parsed_timestamps) if parsed_timestamps else None

    # Source reliability mapping
    source_weights = {
        "metrics": 1.0,
        "logs": 0.8,
        "deployment": 0.9,
        "alert": 0.7,
        "manual": 0.5,
    }

    weighted_items = []
    for item in evidence_items:
        weighted = dict(item)

        # Calculate source reliability weight
        source = item.get("source", "unknown")
        reliability = source_weights.get(source, 0.5)

        # Check completeness (all expected fields present and not empty)
        expected_fields = [
            "item_key",
            "source",
            "timestamp",
            "service",
            "signal",
            "value",
            "severity",
            "confidence",
        ]
        is_complete = True
        for field_name in expected_fields:
            val = item.get(field_name)
            if val is None or val == "":
                is_complete = False
                break

        completeness_multiplier = 1.0 if is_complete else 0.7

        # Calculate recency multiplier
        recency_multiplier = 1.0
        ts = _parse_timestamp(item.get("timestamp"))
        if ts and max_ts:
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            diff_seconds = (max_ts - ts).total_seconds()
            if 0 <= diff_seconds <= 300:  # Within 5 minutes
                recency_multiplier = 1.2

        # Final weight calculation
        weight = reliability * completeness_multiplier * recency_multiplier
        weighted["weight"] = round(weight, 4)

        # Integrity hash
        weighted["raw_data_hash"] = compute_evidence_hash(item)

        weighted_items.append(weighted)

    return weighted_items
