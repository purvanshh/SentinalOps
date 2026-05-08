from fastapi.testclient import TestClient

from main import app


def test_evaluation_summary_route_returns_metrics() -> None:
    client = TestClient(app)

    response = client.get("/evaluations/summary")

    assert response.status_code == 200
    payload = response.json()
    assert "summary" in payload
    assert "classification_accuracy" in payload["summary"]
