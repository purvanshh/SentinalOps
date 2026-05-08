from agents.rootcause_agent.output_schema import RootCauseAnalysis
from evaluation.hallucination_checks.check_citations import check_citations_present


def summarize_rootcause_metrics(result: RootCauseAnalysis, valid_item_keys: set[str]) -> dict[str, float | bool]:
    top_confidence = 0.0
    if result.strongest_hypothesis_index is not None and result.hypotheses:
        top_confidence = result.hypotheses[result.strongest_hypothesis_index].confidence or 0.0
    return {
        "citation_valid": check_citations_present(result, valid_item_keys),
        "top_confidence": top_confidence,
        "hypothesis_count": float(len(result.hypotheses)),
    }
