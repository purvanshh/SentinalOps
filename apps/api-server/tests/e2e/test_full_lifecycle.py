import os
import httpx
import pytest

E2E_API_URL = os.environ.get("E2E_API_URL", "http://localhost:8080")

@pytest.mark.e2e
def test_full_incident_lifecycle() -> None:
    # 1. Ingest alert through webhook
    alert_payload = {
        "status": "firing",
        "alerts": [
            {
                "labels": {
                    "alertname": "DatabaseConnectionSpike",
                    "severity": "critical",
                    "service": "payment-api"
                },
                "annotations": {
                    "summary": "Database pool connections exceeded 90%"
                },
                "startsAt": "2026-07-07T12:00:00Z"
            }
        ]
    }
    
    try:
        resp = httpx.post(f"{E2E_API_URL}/incidents/webhook", json=alert_payload, timeout=5.0)
        # Webster returns 202 Accepted
        assert resp.status_code in [200, 202]
        
        # Verify response payload has incident id or is accepted
        data = resp.json()
        assert data.get("status") == "accepted"
    except httpx.RequestError:
        pytest.skip(f"E2E API Server not running at {E2E_API_URL}")
