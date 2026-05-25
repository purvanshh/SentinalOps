from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

from evaluation.hallucination_checks.check_citations import check_citations_present

ScoringMode = Literal["lexical", "semantic"]

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


def _score_f1(predicted_text: str, expected_text: str) -> float:
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


@lru_cache(maxsize=1)
def _get_embedder():
    from sentence_transformers import SentenceTransformer

    cache_root = Path.home() / ".cache" / "huggingface" / "hub"
    local_snapshot = (
        cache_root
        / "models--sentence-transformers--all-MiniLM-L6-v2"
        / "snapshots"
        / "c9745ed1d9f207416be6d2e6f8de32d1f16199bf"
    )
    if local_snapshot.exists():
        return SentenceTransformer(str(local_snapshot))
    return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


def semantic_similarity(predicted_text: str, expected_text: str) -> float:
    if not predicted_text.strip() or not expected_text.strip():
        return 0.0
    import numpy as np

    embedder = _get_embedder()
    embeddings = embedder.encode([predicted_text, expected_text], convert_to_numpy=True)
    numerator = float(np.dot(embeddings[0], embeddings[1]))
    denominator = float(np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1]))
    if denominator == 0.0:
        return 0.0
    return max(0.0, min(1.0, numerator / denominator))


def _score_semantic(predicted_text: str, expected_text: str) -> float:
    cosine = semantic_similarity(predicted_text, expected_text)
    return float(max(0.0, (cosine - 0.3) / 0.7))


def score_root_cause(
    predicted_text: str,
    expected_text: str,
    mode: ScoringMode = "lexical",
) -> float:
    if mode == "lexical":
        return _score_f1(predicted_text, expected_text)
    if mode == "semantic":
        return _score_semantic(predicted_text, expected_text)
    raise ValueError(f"Unknown scoring mode: {mode}")


def score_grounding(valid_item_keys: set[str], result) -> float:
    return 1.0 if check_citations_present(result, valid_item_keys) else 0.0
