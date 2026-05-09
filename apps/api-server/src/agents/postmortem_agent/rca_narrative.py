from __future__ import annotations

from typing import Any


def build_five_whys_narrative(root_cause: dict[str, Any]) -> str:
    hypotheses = root_cause.get("hypotheses", [])
    index = root_cause.get("strongest_hypothesis_index")
    if index is None or not hypotheses:
        return "Insufficient evidence to construct a 5 Whys narrative."
    top = hypotheses[index]
    evidence_for = top.get("evidence_for", [])
    evidence_refs = ", ".join(item.get("item_key", "?") for item in evidence_for[:3]) or "no evidence refs"
    why_chain = [
        f"1. Why did the incident happen? {top.get('hypothesis', 'Unknown cause')} ({evidence_refs})",
        f"2. Why was the service impacted? {top.get('causal_chain', 'Causal chain unavailable.')}",
        f"3. Why do we believe this? Supporting evidence items: {evidence_refs}.",
        f"4. Why was this not prevented earlier? Counterfactual check: {top.get('counterfactual_test', 'Unavailable')}",
        "5. Why does this matter? The incident exposed a gap in detection, resilience, or rollout safety.",
    ]
    return "\n".join(why_chain)
