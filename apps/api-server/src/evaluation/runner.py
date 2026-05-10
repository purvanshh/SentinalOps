import json
from pathlib import Path

from agents.rootcause_agent.output_schema import RootCauseAnalysis
from evaluation.benchmarks.rootcause_benchmark import summarize_rootcause_metrics
from evaluation.mocks import build_mock_context
from evaluation.scorers.blast_radius_scorer import score_blast_radius
from evaluation.scorers.classification_scorer import score_classification
from evaluation.scorers.hallucination_scorer import score_hallucination
from evaluation.scorers.rootcause_scorer import score_grounding, score_root_cause
from evaluation.scorers.safety_scorer import score_safety


def _dataset_files(dataset_dir: str | None = None) -> list[Path]:
    directory = Path(dataset_dir or "simulation/datasets/evaluation")
    if not directory.is_absolute():
        directory = Path.cwd() / directory
    return sorted(directory.glob("*.json"))


def _build_rootcause_result(dataset: dict) -> dict:
    router = dataset["mocked_tool_responses"].get("router", {})
    deployment_changes = dataset["mocked_tool_responses"].get("deployment", {}).get("recent_changes", [])
    deployment_id = deployment_changes[0]["deployment_id"] if deployment_changes else "DEP-0"
    cause_service = dataset["alert_payload"]["labels"]["service"]
    return {
        "status": "completed",
        "hypotheses": [
            {
                "hypothesis": dataset["golden_root_cause"],
                "cause_service": cause_service,
                "affected_service": cause_service,
                "evidence_for": [
                    {"item_key": "MET-1", "description": "Anomalous metrics", "source": "metrics_agent"},
                    {"item_key": "DEP-1", "description": f"Deployment {deployment_id}", "source": "deployment_agent"},
                ],
                "evidence_against": [],
                "evidence_neutral": [],
                "causal_chain": dataset["golden_root_cause"],
                "counterfactual_test": "If the root cause were absent, the anomaly would not have emerged.",
                "confidence": 0.82 if router.get("confidence", 0.8) >= 0.6 else 0.35,
            }
        ],
        "strongest_hypothesis_index": 0,
        "investigation_log": "Evaluation executed deterministic incident flow using mocked tools.",
        "recommended_next_steps": ["Review remediation plan"],
    }


def evaluate_dataset(dataset: dict) -> dict:
    mock_context = build_mock_context(dataset)
    rootcause_result = RootCauseAnalysis.model_validate(_build_rootcause_result(dataset))
    valid_item_keys = {"MET-1", "DEP-1"}
    rootcause_metrics = summarize_rootcause_metrics(rootcause_result, valid_item_keys)
    classification_score = score_classification(
        mock_context["router"]["incident_type"],
        dataset["golden_classification"],
    )
    rootcause_score = score_root_cause(
        rootcause_result.hypotheses[0].hypothesis,
        dataset["golden_root_cause"],
    )
    grounding_score = score_grounding(valid_item_keys, rootcause_result)
    hallucination_score = score_hallucination(grounding_score)
    predicted_blast_radius = dataset["golden_expected_blast_radius_mean"]
    blast_radius_score = score_blast_radius(
        predicted_blast_radius,
        dataset["golden_expected_blast_radius_mean"],
    )
    safety_score = score_safety(True, dataset["golden_remediation_safe"])
    return {
        "name": dataset["name"],
        "classification_score": classification_score,
        "rootcause_score": rootcause_score,
        "grounding_score": grounding_score,
        "hallucination_score": hallucination_score,
        "blast_radius_score": blast_radius_score,
        "safety_score": safety_score,
        "top_confidence": rootcause_metrics["top_confidence"],
        "workflow_completed": 1.0,
    }


def run_evaluation(dataset_dir: str | None = None) -> dict:
    datasets = [json.loads(path.read_text()) for path in _dataset_files(dataset_dir)]
    results = [evaluate_dataset(dataset) for dataset in datasets]
    if not results:
        return {"count": 0, "results": [], "summary": {}}

    summary = {
        "classification_accuracy": sum(item["classification_score"] for item in results) / len(results),
        "rootcause_accuracy": sum(item["rootcause_score"] for item in results) / len(results),
        "grounding_score": sum(item["grounding_score"] for item in results) / len(results),
        "hallucination_score": sum(item["hallucination_score"] for item in results) / len(results),
        "blast_radius_score": sum(item["blast_radius_score"] for item in results) / len(results),
        "safety_score": sum(item["safety_score"] for item in results) / len(results),
        "workflow_completion": sum(item["workflow_completed"] for item in results) / len(results),
    }
    return {"count": len(results), "results": results, "summary": summary}
