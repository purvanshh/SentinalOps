def score_classification(predicted: str | None, expected: str) -> float:
    if not predicted:
        return 0.0
    return 1.0 if predicted.strip().lower() == expected.strip().lower() else 0.0
