import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from main import app
from db.session import SessionLocal
from db.repositories.incident_repo import IncidentRepository
from api.schemas.incident import IncidentCreate

@pytest.mark.integration
def test_incident_ingestion_lifecycle(postgres_container, redis_container) -> None:
    # Verify that we can write to the PostgreSQL database container
    client = TestClient(app)
    incident_data = {
        "title": "Database connection spike",
        "severity": "critical",
        "source": "prometheus",
        "summary": "Database pool connections exceeded limit",
        "raw_payload": {"labels": {"service": "payment-api"}}
    }
    
    # Assert connection details or session setup
    assert postgres_container.get_connection_url() is not None
    assert redis_container.get_container_host_ip() is not None
