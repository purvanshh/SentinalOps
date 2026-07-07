import pytest
from agents.uncertainty import UncertaintyEngine


def test_uncertainty_engine_confidence_interval() -> None:
    engine = UncertaintyEngine()
    interval = engine.confidence_interval(0.8, 0.2, 0)
    assert interval.lower >= 0.0
    assert interval.upper <= 1.0
    assert interval.lower <= interval.upper


def test_uncertainty_engine_rank_hypotheses() -> None:
    engine = UncertaintyEngine(calibration_temperature=1.0)
    scores = [1.0, 2.0, 3.0]
    probs = engine.rank_hypotheses(scores)
    assert len(probs) == 3
    assert sum(probs) == pytest.approx(1.0)
    assert probs[2] > probs[1] > probs[0]


def test_uncertainty_engine_assess_basic() -> None:
    engine = UncertaintyEngine()
    assessment = engine.assess(
        evidence_items=[{"item_type": "metric", "confidence": 0.9}],
        timed_events=[],
        grounding_score=0.8,
        raw_hypothesis_scores=[2.0, 1.0],
        hypothesis_labels=["deployment_regression", "db_saturation"],
        incident_severity="medium",
    )
    expected_states = [
        "stable",
        "insufficient_telemetry",
        "conflicting_signals",
        "unknown_cause",
        "low_confidence_escalation",
    ]
    assert assessment.state in expected_states
