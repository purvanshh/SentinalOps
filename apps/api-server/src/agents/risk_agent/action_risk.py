from agents.risk_agent.action_mapper import map_action_to_category


def score_remediation_action(
    action: str,
    history: list[dict],
) -> dict:
    category = map_action_to_category(action)
    matching = [item for item in history if item["category"] == category]
    if not matching:
        return {
            "probability_of_success": 0.6,
            "risk_score": 0.55,
            "worst_case_impact": "Unknown action history may increase outage duration.",
            "recommendation": "review manually",
        }

    successes = sum(1 for item in matching if item["success"])
    total = len(matching)
    probability_of_success = (successes + 1) / (total + 2)
    avg_execution_time = sum(item["execution_time_seconds"] for item in matching) / total
    avg_failure_severity = sum(item["severity_on_failure"] for item in matching) / total
    execution_factor = min(avg_execution_time / 300.0, 1.0)
    risk_score = round(
        (1 - probability_of_success) * avg_failure_severity * (1 + execution_factor), 4
    )
    recommendation = "safe to proceed" if risk_score < 0.25 else "avoid unless necessary"
    worst_case_impact = (
        "Brief interruption during mitigation."
        if risk_score < 0.25
        else "Mitigation failure could prolong user impact."
    )
    return {
        "probability_of_success": round(probability_of_success, 4),
        "risk_score": risk_score,
        "base_risk": round(1 - probability_of_success, 4),
        "execution_time_factor": round(execution_factor, 4),
        "severity_on_failure": round(avg_failure_severity, 4),
        "worst_case_impact": worst_case_impact,
        "recommendation": recommendation,
    }
