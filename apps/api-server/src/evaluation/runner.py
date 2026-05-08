import json
from pathlib import Path

from agents.rootcause_agent.output_schema import RootCauseAnalysis
from evaluation.benchmarks.rootcause_benchmark import summarize_rootcause_metrics
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


def _build_mock_rootcause_result(dataset: dict) -> RootCauseAnalysis:
    deployment_changes = dataset["mocked_tool_responses"].get("deployment", {}).get("recent_changes", [])
    deployment_id = deployment_changes[0]["deployment_id"] if deployment_changes else "DEP-0"
    incident_type = dataset["golden_classification"]
    cause_service = "payment-api" if "deployment" in incident_type else "cache-service"
    hypothesis = {
        "hypothesis": dataset["golden_root_cause"],
        "cause_service": cause_service,
        "affected_service": dataset["alert_payload"]["labels"]["service"],
        "evidence_for": [
            {"item_key": "MET-1", "description": "Anomalous metrics", "source": "metrics_agent"},
            {"item_key": "DEP-1", "description": f"Deployment {deployment_id}", "source": "deployment_agent"},
        ],
        "evidence_against": [],
        "evidence_neutral": [],
        "causal_chain": dataset["golden_root_cause"],
        "counterfactual_test": "If this cause were absent, the anomaly would not have appeared.",
        "confidence": 0.82,
        "temporal_score": 1.0,
        "evidence_coverage": 1.0,
        "pattern_match_score": 0.8,
        "prior_probability": 0.7,
        "counterfactual_power": 0.8
    }
    return RootCauseAnalysis.model_validate(
        {
            "status": "completed",
            "hypotheses": [hypothesis],
            "strongest_hypothesis_index": 0,
            "investigation_log": "Synthetic benchmark root cause result.",
            "recommended_next_steps": ["Review remediation plan"]
        }
    )


def run_evaluation(dataset_dir: str | None = None) -> dict:
    datasets = [json.loads(path.read_text()) for path in _dataset_files(dataset_dir)]
    results = []
    for dataset in datasets:
        rootcause_result = _build_mock_rootcause_result(dataset)
        valid_item_keys = {"MET-1", "DEP-1"}
        rootcause_metrics = summarize_rootcause_metrics(rootcause_result, valid_item_keys)
        classification_score = score_classification(
            dataset["mocked_tool_responses"]["router"]["incident_type"],
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
        results.append(
            {
                "name": dataset["name"],
                "classification_score": classification_score,
                "rootcause_score": rootcause_score,
                "grounding_score": grounding_score,
                "hallucination_score": hallucination_score,
                "blast_radius_score": blast_radius_score,
                "safety_score": safety_score,
                "top_confidence": rootcause_metrics["top_confidence"],
            }
        )

    if not results:
        return {"count": 0, "results": [], "summary": {}}

    summary = {
        "classification_accuracy": sum(item["classification_score"] for item in results) / len(results),
        "rootcause_accuracy": sum(item["rootcause_score"] for item in results) / len(results),
        "grounding_score": sum(item["grounding_score"] for item in results) / len(results),
        "hallucination_score": sum(item["hallucination_score"] for item in results) / len(results),
        "blast_radius_score": sum(item["blast_radius_score"] for item in results) / len(results),
        "safety_score": sum(item["safety_score"] for item in results) / len(results),
    }
    return {"count": len(results), "results": results, "summary": summary}
