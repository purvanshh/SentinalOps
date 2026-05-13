from __future__ import annotations

from datetime import datetime
from typing import Any


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def compute_incident_metrics(
    alert_time: datetime | None,
    evidence_items: list[Any],
    remediation_actions: list[Any],
    resolved_at: datetime | None,
) -> dict[str, Any]:
    anomaly_times = []
    for item in evidence_items:
        raw = (item.content or {}).get("timestamp") if hasattr(item, "content") else None
        parsed = _parse_time(raw)
        if parsed is not None:
            anomaly_times.append(parsed)
    first_anomaly = min(anomaly_times) if anomaly_times else alert_time

    mitigated_candidates = [
        action.updated_at for action in remediation_actions if getattr(action, "executed", False)
    ]
    mitigated_at = min(mitigated_candidates) if mitigated_candidates else None

    ttd = (alert_time - first_anomaly).total_seconds() if alert_time and first_anomaly else None
    ttm = (mitigated_at - alert_time).total_seconds() if alert_time and mitigated_at else None
    ttr = (resolved_at - alert_time).total_seconds() if alert_time and resolved_at else None

    return {
        "first_anomaly_at": first_anomaly.isoformat() if first_anomaly else None,
        "mitigated_at": mitigated_at.isoformat() if mitigated_at else None,
        "resolved_at": resolved_at.isoformat() if resolved_at else None,
        "ttd_seconds": ttd,
        "ttm_seconds": ttm,
        "ttr_seconds": ttr,
    }
