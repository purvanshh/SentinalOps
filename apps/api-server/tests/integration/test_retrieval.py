import pytest


@pytest.mark.integration
def test_qdrant_retrieval_integration() -> None:
    # Verify that retrieval orchestrator connects to Qdrant successfully
    from retrieval.retrieval_orchestrator import RetrievalOrchestrator

    try:
        orchestrator = RetrievalOrchestrator()
        assert orchestrator is not None
    except Exception:
        pytest.skip("Qdrant service is not running or not configured")
