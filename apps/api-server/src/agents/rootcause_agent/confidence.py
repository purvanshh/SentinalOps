import json
from pathlib import Path


def load_rootcause_weights(path: str | None = None) -> dict[str, float]:
    weights_path = Path(path or "configs/development/rootcause_weights.yaml")
    if not weights_path.is_absolute():
        weights_path = Path.cwd() / weights_path
    if not weights_path.exists():
        return {
            "evidence_coverage": 0.3,
            "temporal_score": 0.2,
            "pattern_match_score": 0.2,
            "prior_probability": 0.15,
            "counterfactual_power": 0.15,
        }

    # Keep parsing dependency-free for this stage.
    raw = weights_path.read_text().splitlines()
    weights: dict[str, float] = {}
    for line in raw:
        stripped = line.strip()
        if not stripped or stripped.startswith("weights:"):
            continue
        key, value = stripped.split(":")
        weights[key.strip()] = float(value.strip())
    return weights


def compute_confidence(
    *,
    evidence_coverage: float,
    temporal_score: float,
    pattern_match_score: float,
    prior_probability: float,
    counterfactual_power: float,
    weights: dict[str, float] | None = None,
) -> float:
    configured_weights = weights or load_rootcause_weights()
    return round(
        evidence_coverage * configured_weights["evidence_coverage"]
        + temporal_score * configured_weights["temporal_score"]
        + pattern_match_score * configured_weights["pattern_match_score"]
        + prior_probability * configured_weights["prior_probability"]
        + counterfactual_power * configured_weights["counterfactual_power"],
        4,
    )
