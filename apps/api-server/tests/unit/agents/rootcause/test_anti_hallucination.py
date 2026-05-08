from agents.rootcause_agent.causal_validator import check_temporal_order, is_valid_path
from orchestration.state.topology_schema import ServiceNode


def test_rejects_impossible_causal_path() -> None:
    topology = {
        "payment-api": ServiceNode(name="payment-api", depends_on=["postgres-db"]),
        "postgres-db": ServiceNode(name="postgres-db", depends_on=[]),
        "cache-service": ServiceNode(name="cache-service", depends_on=[]),
    }

    assert is_valid_path("cache-service", "payment-api", topology) is False


def test_detects_temporal_violation() -> None:
    evidence = [
        {"timestamp": "2026-05-08T14:03:10Z"},
        {"timestamp": "2026-05-08T14:02:55Z"},
    ]

    assert check_temporal_order(evidence) is False
