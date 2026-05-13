from agents.postmortem_agent.contributing_factors import evaluate_contributing_factors


def test_contributing_factors_detects_deployments_and_logs() -> None:
    result = evaluate_contributing_factors(
        {
            "deployment": {
                "recent_changes": [{"deployment_id": "DEP-1"}],
                "correlation_with_incident": "Deploy preceded issue.",
            },
            "metrics": {"summary": "Latency increased after deployment."},
            "logs": {"error_signatures": [{"signature": "TimeoutException"}]},
        }
    )

    assert any(item["detected"] for item in result)
