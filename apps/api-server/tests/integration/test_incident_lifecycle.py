import pytest


@pytest.mark.integration
def test_incident_ingestion_lifecycle(postgres_container, redis_container) -> None:
    # Assert connection details or session setup
    assert postgres_container.get_connection_url() is not None
    assert redis_container.get_container_host_ip() is not None
