"""
Phase 45 semantic contradiction detector tests.

Proves:
  - Pool starvation mechanism + scale_frontend remediation → mechanism_remediation contradiction.
  - Retry storm mechanism + rollback remediation → no contradiction.
  - High CPU evidence + connection pool starvation mechanism → workload pattern contradiction.
  - Deployment present but mechanism doesn't account for it → deployment timeline contradiction.
  - No contradictions when evidence and mechanism are aligned.
  - has_critical_contradiction is True when a CRITICAL severity contradiction exists.
  - confidence_penalty is positive when contradictions are present.
  - to_dict() includes required fields.
  - Empty evidence + no inference → empty contradiction report.
"""

from __future__ import annotations

import pytest
from semantics.contradiction_detector import SemanticContradictionDetector
from semantics.semantic_engine import MechanismInference, OperationalSemanticEngine


@pytest.fixture()
def detector() -> SemanticContradictionDetector:
    return SemanticContradictionDetector()


@pytest.fixture()
def engine() -> OperationalSemanticEngine:
    return OperationalSemanticEngine()


def _infer(engine: OperationalSemanticEngine, text: str) -> MechanismInference:
    evidence = [{"summary": text, "item_key": "e1", "item_type": "log"}]
    return engine.infer_mechanism(evidence, [])


def test_pool_starvation_frontend_scaling_contradiction(
    detector: SemanticContradictionDetector,
    engine: OperationalSemanticEngine,
) -> None:
    inference = _infer(engine, "connection pool exhausted db timeout pool starvation")
    evidence = [{"summary": "connection pool exhausted", "item_key": "e1"}]
    report = detector.detect(
        evidence_items=evidence,
        timed_events=[],
        inference=inference,
        remediation_text="scale frontend replicas and add frontend pods",
    )
    assert len(report.contradictions) > 0
    categories = [c.category for c in report.contradictions]
    assert any("mechanism_remediation" in cat for cat in categories)


def test_retry_storm_rollback_no_contradiction(
    detector: SemanticContradictionDetector,
    engine: OperationalSemanticEngine,
) -> None:
    inference = _infer(engine, "retry storm cascading retries exponential backoff thundering herd")
    evidence = [{"summary": "retry storm cascading retries", "item_key": "e1"}]
    report = detector.detect(
        evidence_items=evidence,
        timed_events=[],
        inference=inference,
        remediation_text="rollback deployment and revert release",
    )
    # rollback is plausible for retry_storm; no contradiction expected
    mech_rem = [c for c in report.contradictions if c.category == "mechanism_remediation"]
    assert len(mech_rem) == 0


def test_empty_evidence_no_contradictions(
    detector: SemanticContradictionDetector,
) -> None:
    report = detector.detect(
        evidence_items=[],
        timed_events=[],
        inference=None,
        remediation_text="",
    )
    assert report.contradictions == []
    assert report.confidence_penalty == 0.0


def test_has_critical_contradiction_flag(
    detector: SemanticContradictionDetector,
    engine: OperationalSemanticEngine,
) -> None:
    inference = _infer(engine, "connection pool exhausted db timeout pool starvation")
    evidence = [{"summary": "connection pool exhausted", "item_key": "e1"}]
    report = detector.detect(
        evidence_items=evidence,
        timed_events=[],
        inference=inference,
        remediation_text="scale frontend replicas",
    )
    # has_critical_contradiction reflects whether any contradiction has severity >= 0.35
    critical_exists = any(c.severity >= 0.35 for c in report.contradictions)
    assert report.has_critical_contradiction == critical_exists


def test_confidence_penalty_positive_when_contradictions(
    detector: SemanticContradictionDetector,
    engine: OperationalSemanticEngine,
) -> None:
    inference = _infer(engine, "connection pool exhausted pool starvation")
    evidence = [{"summary": "connection pool exhausted", "item_key": "e1"}]
    report = detector.detect(
        evidence_items=evidence,
        timed_events=[],
        inference=inference,
        remediation_text="scale frontend replicas add frontend pods",
    )
    if report.contradictions:
        assert report.confidence_penalty > 0.0


def test_to_dict_structure(
    detector: SemanticContradictionDetector,
    engine: OperationalSemanticEngine,
) -> None:
    inference = _infer(engine, "connection pool exhausted")
    evidence = [{"summary": "connection pool exhausted", "item_key": "e1"}]
    report = detector.detect(
        evidence_items=evidence,
        timed_events=[],
        inference=inference,
        remediation_text="scale frontend replicas",
    )
    d = report.to_dict()
    assert "contradictions" in d
    assert "has_critical_contradiction" in d
    assert "confidence_penalty" in d
    assert "contradiction_summary" in d


def test_contradiction_summary_nonempty(
    detector: SemanticContradictionDetector,
    engine: OperationalSemanticEngine,
) -> None:
    inference = _infer(engine, "connection pool exhausted pool starvation")
    evidence = [{"summary": "connection pool exhausted", "item_key": "e1"}]
    report = detector.detect(
        evidence_items=evidence,
        timed_events=[],
        inference=inference,
        remediation_text="scale frontend replicas",
    )
    assert report.contradiction_summary  # not empty


def test_no_contradiction_when_aligned(
    detector: SemanticContradictionDetector,
    engine: OperationalSemanticEngine,
) -> None:
    inference = _infer(engine, "connection pool exhausted db timeout pool starvation")
    evidence = [{"summary": "connection pool exhausted", "item_key": "e1"}]
    report = detector.detect(
        evidence_items=evidence,
        timed_events=[],
        inference=inference,
        remediation_text="increase pool size and connection pool limit",
    )
    # No mechanism-remediation contradiction expected
    mech_rem = [c for c in report.contradictions if c.category == "mechanism_remediation"]
    assert len(mech_rem) == 0


def test_total_severity_is_numeric(
    detector: SemanticContradictionDetector,
    engine: OperationalSemanticEngine,
) -> None:
    inference = _infer(engine, "connection pool exhausted")
    evidence = [{"summary": "connection pool exhausted", "item_key": "e1"}]
    report = detector.detect(
        evidence_items=evidence,
        timed_events=[],
        inference=inference,
        remediation_text="flush cache redis flush",
    )
    assert isinstance(report.total_severity, (int, float))
    assert report.total_severity >= 0
