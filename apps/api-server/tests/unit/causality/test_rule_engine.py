from __future__ import annotations

from causality.rule_engine import RuleEngine


def test_rule_engine_loading() -> None:
    engine = RuleEngine()
    assert len(engine.rules) == 9

    categories = {r.category for r in engine.rules}
    assert "database_failure" in categories
    assert "memory_pressure" in categories
    assert "deployment_regression" in categories


def test_rule_engine_evaluate_database() -> None:
    engine = RuleEngine()
    evidence = [
        {
            "item_key": "EVID-1",
            "source": "metrics",
            "signal": "db_response_time_spike",
            "severity": "critical",
        }
    ]
    matches = engine.evaluate(evidence)
    assert len(matches) > 0
    # Top match should be database failure id
    matched_ids = {m.rule.id for m in matches}
    assert "db_slow_query" in matched_ids


def test_rule_engine_evaluate_memory() -> None:
    engine = RuleEngine()
    evidence = [
        {
            "item_key": "EVID-1",
            "source": "logs",
            "signal": "out_of_memory_error",
            "severity": "critical",
        }
    ]
    matches = engine.evaluate(evidence)
    assert len(matches) > 0
    matched_ids = {m.rule.id for m in matches}
    assert "oom_kill_detected" in matched_ids


def test_rule_engine_conflict_resolution() -> None:
    engine = RuleEngine()
    # Provide evidence that triggers both database slow query (resource_exhaustion)
    # and database transaction lock (dependency_failure)
    evidence = [
        {
            "item_key": "EVID-1",
            "source": "metrics",
            "signal": "db_response_time_spike",
            "severity": "critical",
        },
        {
            "item_key": "EVID-2",
            "source": "logs",
            "signal": "deadlock_detected",
            "severity": "critical",
        },
    ]
    matches = engine.evaluate(evidence)
    assert len(matches) >= 2
    # Verify confidences have been scaled down (e.g. 0.75 * 0.8 = 0.6)
    for m in matches:
        if m.rule.id == "db_slow_query":
            assert m.confidence == 0.6
        elif m.rule.id == "db_transaction_lock":
            assert m.confidence == 0.56
