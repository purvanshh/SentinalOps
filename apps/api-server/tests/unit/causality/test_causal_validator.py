from causality.validators.causal_validator import (
    ServiceNode,
    check_service_references,
    check_temporal_order,
    is_valid_path,
    service_exists,
)


def test_service_exists() -> None:
    topology = {"payment-api": ServiceNode(name="payment-api", depends_on=[])}
    assert service_exists("payment-api", topology)
    assert not service_exists("unknown-service", topology)


def test_check_service_references() -> None:
    topology = {"payment-api": ServiceNode(name="payment-api", depends_on=[])}
    violations = check_service_references(["payment-api", "missing-service"], topology)
    assert len(violations) == 1
    assert violations[0].service == "missing-service"


def test_is_valid_path() -> None:
    # Set up simple topology: backend depends on database
    # path from backend (cause) to database (effect) should be valid
    topology = {
        "backend": ServiceNode(name="backend", depends_on=["database"]),
        "database": ServiceNode(name="database", depends_on=[]),
    }
    assert is_valid_path("database", "backend", topology)
    assert not is_valid_path("backend", "database", topology)


def test_check_temporal_order() -> None:
    items = [{"timestamp": "2026-05-29T12:00:00Z"}, {"timestamp": "2026-05-29T12:05:00Z"}]
    assert check_temporal_order(items)

    out_of_order = [{"timestamp": "2026-05-29T12:05:00Z"}, {"timestamp": "2026-05-29T12:00:00Z"}]
    assert not check_temporal_order(out_of_order)
