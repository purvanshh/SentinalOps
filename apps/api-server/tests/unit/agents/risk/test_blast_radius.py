from agents.risk_agent.blast_radius import compute_blast_radius
from orchestration.state.topology_schema import ServiceNode


def test_compute_blast_radius_returns_distribution() -> None:
    topology = {
        "postgres-db": ServiceNode(name="postgres-db", depends_on=[]),
        "payment-api": ServiceNode(name="payment-api", depends_on=["postgres-db"]),
        "checkout-api": ServiceNode(name="checkout-api", depends_on=["payment-api"]),
    }
    traffic = {
        "postgres-db": {"rps": 400},
        "payment-api": {"rps": 300},
        "checkout-api": {"rps": 200},
    }

    result = compute_blast_radius("postgres-db", topology, traffic, severity_factor=0.2, samples=200)

    assert "payment-api" in result["affected_services"]
    assert result["users_at_risk"]["mean"] > 0
