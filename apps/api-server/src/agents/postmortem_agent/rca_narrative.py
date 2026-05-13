from __future__ import annotations

from typing import Any


def build_five_whys_narrative(root_cause: dict[str, Any]) -> str:
    hypotheses = root_cause.get("hypotheses", [])
    index = root_cause.get("strongest_hypothesis_index")
    if index is None or not hypotheses:
        return "Insufficient evidence to construct a 5 Whys narrative."
    top = hypotheses[index]
    uncertainty = root_cause.get("uncertainty", {})
    evidence_for = top.get("evidence_for", [])
    evidence_refs = (
        ", ".join(item.get("item_key", "?") for item in evidence_for[:3]) or "no evidence refs"
    )
    alternatives = (
        ", ".join(root_cause.get("contributing_causes", [])[1:3]) or "no strong alternatives"
    )
    confidence = top.get("probability", top.get("confidence", 0.0))
    why_chain = [
        "1. Why did the incident happen? "
        f"{top.get('hypothesis', 'Unknown cause')} "
        f"({confidence:.0%} confidence; evidence: {evidence_refs})",
        f"2. Why was the service impacted? {top.get('causal_chain', 'Causal chain unavailable.')}",
        f"3. Why do we believe this? Supporting evidence items: {evidence_refs}.",
        "4. Why was this not prevented earlier? Counterfactual check: "
        f"{top.get('counterfactual_test', 'Unavailable')}",
        "5. Why does this matter? The incident exposed a gap in "
        "detection, resilience, or rollout safety.",
    ]
    if uncertainty:
        why_chain.append(
            "Uncertainty: "
            f"{uncertainty.get('state', 'stable')} with alternative explanations including "
            f"{alternatives}."
        )
    return "\n".join(why_chain)
