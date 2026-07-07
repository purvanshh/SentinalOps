import pytest

try:
    from testcontainers.postgres import PostgresContainer
    from testcontainers.redis import RedisContainer

    HAS_TESTCONTAINERS = True
except ImportError:
    HAS_TESTCONTAINERS = False

if HAS_TESTCONTAINERS:

    @pytest.fixture(scope="session")
    def postgres_container():
        with PostgresContainer("postgres:15.6") as postgres:
            yield postgres

    @pytest.fixture(scope="session")
    def redis_container():
        with RedisContainer("redis:7.2.4") as redis:
            yield redis

else:

    @pytest.fixture(scope="session")
    def postgres_container():
        pytest.skip("testcontainers not installed")

    @pytest.fixture(scope="session")
    def redis_container():
        pytest.skip("testcontainers not installed")


def pytest_collection_modifyitems(items):
    for item in items:
        # Check if the test is inside the integration folder
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
