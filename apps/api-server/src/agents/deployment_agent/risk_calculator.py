def calculate_deployment_risk(change_type: str, minutes_since_deploy: int, prior_incident_match: bool) -> float:
    base_score_map = {
        "infrastructure": 0.8,
        "database": 0.85,
        "backend": 0.7,
        "frontend": 0.35,
        "config": 0.65,
        "unknown": 0.5,
    }
    score = base_score_map.get(change_type, base_score_map["unknown"])
    if minutes_since_deploy <= 15:
        score += 0.1
    if prior_incident_match:
        score += 0.1
    return min(score, 0.99)
