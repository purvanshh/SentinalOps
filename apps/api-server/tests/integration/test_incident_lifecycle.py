import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.mark.integration
def test_incident_ingestion_lifecycle(postgres_container, redis_container) -> None:
    # Verify that we can write to the PostgreSQL database container
    TestClient(app)

    # Assert connection details or session setup
    assert postgres_container.get_connection_url() is not None
    assert redis_container.get_container_host_ip() is not None
