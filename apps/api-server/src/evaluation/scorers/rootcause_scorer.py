from __future__ import annotations

import re

from evaluation.hallucination_checks.check_citations import check_citations_present

_STOPWORDS = {
    "the",
    "a",
    "an",
    "of",
    "to",
    "and",
    "in",
    "on",
    "for",
    "with",
    "service",
    "issue",
    "failure",
    "outage",
    "incident",
    "likely",
    "cause",
    "contributor",
    "impact",
    "observed",
}


def _normalize_tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z][a-z0-9_-]+", text.lower())
        if token not in _STOPWORDS and len(token) > 2
    }


def score_root_cause(predicted_text: str, expected_text: str) -> float:
    predicted = predicted_text.lower()
    expected = expected_text.lower()
    if not predicted or not expected:
        return 0.0
    if expected in predicted or predicted in expected:
        return 1.0

    predicted_tokens = _normalize_tokens(predicted_text)
    expected_tokens = _normalize_tokens(expected_text)
    if not predicted_tokens or not expected_tokens:
        return 0.0

    overlap = predicted_tokens & expected_tokens
    precision = len(overlap) / len(predicted_tokens)
    recall = len(overlap) / len(expected_tokens)
    if precision + recall == 0:
        return 0.0
    return round((2 * precision * recall) / (precision + recall), 4)


def score_grounding(valid_item_keys: set[str], result) -> float:
    return 1.0 if check_citations_present(result, valid_item_keys) else 0.0
