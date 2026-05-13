import pytest

from evaluation.runner import run_evaluation


@pytest.mark.asyncio
async def test_evaluation_runner_returns_summary() -> None:
    result = await run_evaluation()

    assert result["count"] >= 2
    assert "summary" in result
    assert "classification_accuracy" in result["summary"]
    assert "workflow_completion" in result["summary"]
    assert len(result["results"]) == result["count"]
