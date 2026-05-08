def score_safety(remediation_safe: bool, expected_safe: bool) -> float:
    return 1.0 if remediation_safe == expected_safe else 0.0
