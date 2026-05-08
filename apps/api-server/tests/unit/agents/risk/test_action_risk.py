from agents.risk_agent.action_risk import score_remediation_action


def test_action_risk_increases_for_weaker_history() -> None:
    history = [
        {
            "category": "service_restart",
            "success": False,
            "execution_time_seconds": 180.0,
            "severity_on_failure": 0.8,
        },
        {
            "category": "service_restart",
            "success": True,
            "execution_time_seconds": 150.0,
            "severity_on_failure": 0.8,
        },
    ]

    result = score_remediation_action("restart payment-api", history)

    assert result["risk_score"] > 0.0
    assert result["probability_of_success"] < 0.8
