from evaluation.hallucination_checks.check_citations import check_citations_present


def score_root_cause(predicted_text: str, expected_text: str) -> float:
    predicted = predicted_text.lower()
    expected = expected_text.lower()
    return 1.0 if expected in predicted or predicted in expected else 0.0


def score_grounding(valid_item_keys: set[str], result) -> float:
    return 1.0 if check_citations_present(result, valid_item_keys) else 0.0
