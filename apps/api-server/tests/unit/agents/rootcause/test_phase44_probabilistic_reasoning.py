from __future__ import annotations

from datetime import datetime

from agents.rootcause_agent.causal_graph import CandidateCause
from agents.rootcause_agent.evidence_builder import TimedEvent
from agents.rootcause_agent.probabilistic_reasoner import (
    build_probabilistic_root_cause_analysis,
)
from agents.uncertainty import CONFLICTING_SIGNALS, INSUFFICIENT_TELEMETRY


def _event(
    *,
    item_key: str,
    item_type: str,
    summary: str,
    timestamp: str,
    source: str = "test",
    service: str = "payment-api",
) -> TimedEvent:
    return TimedEvent(
        item_key=item_key,
        source=source,
        item_type=item_type,
        service=service,
        summary=summary,
        timestamp=datetime.fromisoformat(timestamp.replace("Z", "+00:00")),
        payload={},
    )


def _candidate(
    title: str,
    *,
    cause_service: str = "payment-api",
    affected_service: str = "payment-api",
    match_score: float = 0.75,
    required_keywords: list[str] | None = None,
) -> CandidateCause:
    return CandidateCause(
        pattern_id=title.lower().replace(" ", "_"),
        title=title,
        cause_service=cause_service,
        affected_service=affected_service,
        pattern_match_score=match_score,
        required_keywords=required_keywords or [],
        supporting_item_keys=[],
    )


def test_conflicting_evidence_generates_competing_hypotheses_and_escalation() -> None:
    evidence_items = [
        {
            "item_key": "metric-1",
            "source": "metrics",
            "item_type": "metric_anomaly",
            "metric": "db_pool_wait",
            "observed": "high",
            "confidence": 0.91,
        },
        {
            "item_key": "deploy-1",
            "source": "deployments",
            "item_type": "deployment_change",
            "commit_summary": "deployment regression in checkout path",
            "confidence": 0.74,
        },
        {
            "item_key": "log-1",
            "source": "logs",
            "item_type": "error_signature",
            "signature": "postgres timeout while serving checkout",
            "confidence": 0.88,
        },
    ]
    timed_events = [
        _event(
            item_key="metric-1",
            item_type="metric_anomaly",
            summary="postgres connection pool saturation",
            timestamp="2026-05-13T10:00:00Z",
            source="metrics",
        ),
        _event(
            item_key="deploy-1",
            item_type="deployment_change",
            summary="deployment regression shipped to payment-api",
            timestamp="2026-05-13T10:05:00Z",
            source="deployments",
        ),
        _event(
            item_key="log-1",
            item_type="error_signature",
            summary="postgres timeout errors on checkout",
            timestamp="2026-05-13T10:02:00Z",
            source="logs",
        ),
    ]
    result = build_probabilistic_root_cause_analysis(
        incident_type="database_latency",
        incident_severity="critical",
        service="payment-api",
        evidence_items=evidence_items,
        timed_events=timed_events,
        candidates=[
            _candidate(
                "Postgres saturation",
                required_keywords=["postgres", "pool", "timeout"],
                match_score=0.82,
            ),
            _candidate(
                "Deployment regression",
                required_keywords=["deployment", "regression"],
                match_score=0.79,
            ),
        ],
        grounding_score=0.72,
    )

    assert result.uncertainty is not None
    assert result.uncertainty.state == CONFLICTING_SIGNALS
    assert result.escalation is not None and result.escalation.recommended is True
    assert len(result.hypotheses) == 2
    assert result.multi_cause is True
    assert len(result.contributing_causes) >= 2
    assert "confidence" in result.narrative.lower()


def test_missing_metrics_collapses_confidence_and_marks_insufficient_telemetry() -> None:
    evidence_items = [
        {
            "item_key": "log-1",
            "source": "logs",
            "item_type": "error_signature",
            "signature": "gateway timeout",
            "confidence": 0.61,
        }
    ]
    timed_events = [
        _event(
            item_key="log-1",
            item_type="error_signature",
            summary="gateway timeout",
            timestamp="2026-05-13T10:00:00Z",
            source="logs",
        )
    ]
    result = build_probabilistic_root_cause_analysis(
        incident_type="unknown",
        incident_severity="high",
        service="payment-api",
        evidence_items=evidence_items,
        timed_events=timed_events,
        candidates=[_candidate("Unknown service degradation", match_score=0.25)],
        grounding_score=0.2,
    )

    assert result.uncertainty is not None
    assert result.uncertainty.state == INSUFFICIENT_TELEMETRY
    assert result.uncertainty.confidence < 0.35
    assert "metrics" in result.uncertainty.missing_telemetry
    assert result.escalation is not None and result.escalation.recommended is True


def test_weak_grounding_prevents_over_specific_claims() -> None:
    evidence_items = [
        {
            "item_key": "metric-1",
            "source": "metrics",
            "item_type": "metric_anomaly",
            "metric": "latency",
            "observed": "high",
            "confidence": 0.55,
        },
        {
            "item_key": "log-1",
            "source": "logs",
            "item_type": "error_signature",
            "signature": "timeout",
            "confidence": 0.52,
        },
    ]
    timed_events = [
        _event(
            item_key="metric-1",
            item_type="metric_anomaly",
            summary="latency spike",
            timestamp="2026-05-13T10:00:00Z",
            source="metrics",
        ),
        _event(
            item_key="log-1",
            item_type="error_signature",
            summary="timeout",
            timestamp="2026-05-13T10:01:00Z",
            source="logs",
        ),
    ]
    result = build_probabilistic_root_cause_analysis(
        incident_type="unknown",
        incident_severity="medium",
        service="payment-api",
        evidence_items=evidence_items,
        timed_events=timed_events,
        candidates=[_candidate("Unknown service degradation", match_score=0.15)],
        grounding_score=0.1,
    )

    assert result.uncertainty is not None
    assert result.uncertainty.confidence < 0.3
    assert result.status in {"low_confidence_escalation", "unknown_cause"}
