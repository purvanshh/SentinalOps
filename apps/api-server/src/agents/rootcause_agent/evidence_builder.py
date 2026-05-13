from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(slots=True)
class TimedEvent:
    item_key: str
    source: str
    item_type: str
    service: str
    summary: str
    timestamp: datetime | None
    payload: dict[str, Any]


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _derive_service(item: dict[str, Any], default_service: str) -> str:
    return (
        item.get("service")
        or item.get("payload", {}).get("service")
        or item.get("cause_service")
        or item.get("affected_service")
        or default_service
    )


def _derive_summary(item: dict[str, Any]) -> str:
    if item.get("item_type") == "metric_anomaly":
        return f"{item.get('metric', 'metric')} observed {item.get('observed', 'unknown')}"
    if item.get("item_type") == "error_signature":
        return item.get("signature", "log error")
    if item.get("item_type") == "deployment_change":
        return item.get("commit_summary", item.get("deployment_id", "deployment change"))
    return item.get("description", item.get("item_key", "evidence item"))


def build_timed_events(
    evidence_items: list[dict[str, Any]], default_service: str
) -> list[TimedEvent]:
    events: list[TimedEvent] = []
    for item in evidence_items:
        payload = dict(item)
        timestamp = _parse_timestamp(payload.get("timestamp"))
        events.append(
            TimedEvent(
                item_key=payload["item_key"],
                source=payload["source"],
                item_type=payload["item_type"],
                service=_derive_service(payload, default_service),
                summary=_derive_summary(payload),
                timestamp=timestamp,
                payload=payload,
            )
        )
    events.sort(key=lambda event: event.timestamp or datetime.min.replace(tzinfo=UTC))
    return events
