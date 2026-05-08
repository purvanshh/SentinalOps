from agents.rootcause_agent.output_schema import RootCauseAnalysis


def check_citations_present(result: RootCauseAnalysis, valid_item_keys: set[str]) -> bool:
    for hypothesis in result.hypotheses:
        for bucket in (hypothesis.evidence_for, hypothesis.evidence_against, hypothesis.evidence_neutral):
            for item in bucket:
                if item.item_key not in valid_item_keys:
                    return False
    return True
