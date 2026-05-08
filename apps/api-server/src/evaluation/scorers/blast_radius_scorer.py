def score_blast_radius(predicted_mean: int, expected_mean: int) -> float:
    if expected_mean <= 0:
        return 1.0
    error = abs(predicted_mean - expected_mean) / expected_mean
    return max(0.0, 1.0 - error)
