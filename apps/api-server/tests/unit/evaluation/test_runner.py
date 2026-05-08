from evaluation.runner import run_evaluation


def test_evaluation_runner_returns_summary() -> None:
    result = run_evaluation()

    assert result["count"] >= 2
    assert "summary" in result
    assert "classification_accuracy" in result["summary"]
