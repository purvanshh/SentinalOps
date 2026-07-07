"""
Tests for the Phase 39 benchmark incident suite.

Validates:
- Suite loads with >= 100 incidents
- All required fields present
- No duplicate IDs
- Schema validity
- Deterministic loading (reproducibility)
"""

import pytest
from evaluation.benchmark_suite import (
    OPERATOR_ACTIONS,
    REMEDIATION_CLASSES,
    RISK_TIERS,
    BenchmarkSuite,
    load_benchmark_suite,
    validate_suite,
)


@pytest.fixture(scope="module")
def suite() -> BenchmarkSuite:
    return load_benchmark_suite()


class TestBenchmarkSuiteLoading:
    def test_suite_loads_without_error(self, suite: BenchmarkSuite) -> None:
        assert suite is not None

    def test_suite_has_at_least_100_incidents(self, suite: BenchmarkSuite) -> None:
        assert (
            suite.total_incidents >= 100
        ), f"Expected >= 100 incidents, got {suite.total_incidents}"

    def test_suite_incident_count_matches_metadata(self, suite: BenchmarkSuite) -> None:
        assert suite.total_incidents == len(suite.incidents)

    def test_suite_has_suite_id(self, suite: BenchmarkSuite) -> None:
        assert suite.suite_id and len(suite.suite_id) > 0

    def test_suite_has_version(self, suite: BenchmarkSuite) -> None:
        assert suite.version and len(suite.version) > 0

    def test_suite_has_categories(self, suite: BenchmarkSuite) -> None:
        assert len(suite.categories) >= 10, "Expected at least 10 incident categories"

    def test_validation_passes(self, suite: BenchmarkSuite) -> None:
        errors = validate_suite(suite)
        assert errors == [], f"Validation errors: {errors}"

    def test_loading_is_deterministic(self) -> None:
        suite1 = load_benchmark_suite()
        suite2 = load_benchmark_suite()
        ids1 = [inc.id for inc in suite1.incidents]
        ids2 = [inc.id for inc in suite2.incidents]
        assert ids1 == ids2, "Benchmark loading is not deterministic"


class TestBenchmarkIncidentSchema:
    def test_all_incidents_have_ids(self, suite: BenchmarkSuite) -> None:
        for inc in suite.incidents:
            assert inc.id, f"Incident missing id: {inc.name}"

    def test_no_duplicate_ids(self, suite: BenchmarkSuite) -> None:
        ids = [inc.id for inc in suite.incidents]
        assert len(ids) == len(set(ids)), "Duplicate incident IDs found"

    def test_all_incidents_have_golden_classification(self, suite: BenchmarkSuite) -> None:
        for inc in suite.incidents:
            assert inc.golden_classification, f"{inc.id}: missing golden_classification"

    def test_all_incidents_have_valid_remediation_class(self, suite: BenchmarkSuite) -> None:
        for inc in suite.incidents:
            assert (
                inc.golden_remediation_class in REMEDIATION_CLASSES
            ), f"{inc.id}: invalid remediation class '{inc.golden_remediation_class}'"

    def test_all_incidents_have_valid_risk_tier(self, suite: BenchmarkSuite) -> None:
        for inc in suite.incidents:
            assert inc.risk_tier in RISK_TIERS, f"{inc.id}: invalid risk tier '{inc.risk_tier}'"

    def test_all_incidents_have_valid_operator_action(self, suite: BenchmarkSuite) -> None:
        for inc in suite.incidents:
            assert (
                inc.golden_operator_action in OPERATOR_ACTIONS
            ), f"{inc.id}: invalid operator action '{inc.golden_operator_action}'"

    def test_all_incidents_have_confidence_range(self, suite: BenchmarkSuite) -> None:
        for inc in suite.incidents:
            assert (
                0.0 <= inc.confidence_min <= inc.confidence_max <= 1.0
            ), f"{inc.id}: invalid confidence range {inc.expected_confidence_range}"

    def test_all_incidents_have_non_negative_blast_radius(self, suite: BenchmarkSuite) -> None:
        for inc in suite.incidents:
            assert inc.golden_expected_blast_radius_mean >= 0, f"{inc.id}: negative blast radius"

    def test_all_incidents_have_alert_payload(self, suite: BenchmarkSuite) -> None:
        for inc in suite.incidents:
            assert inc.alert_payload, f"{inc.id}: missing alert_payload"
            assert "title" in inc.alert_payload, f"{inc.id}: alert_payload missing title"
            assert "severity" in inc.alert_payload, f"{inc.id}: alert_payload missing severity"


class TestBenchmarkCoverage:
    REQUIRED_CATEGORIES = {
        "latency_spike",
        "deployment_regression",
        "memory_leak",
        "cpu_saturation",
        "redis_outage",
        "postgresql_failure",
        "networking_failure",
        "cascading_failure",
        "noisy_alert",
        "false_positive",
        "disk_exhaustion",
        "kubernetes_pod_failure",
        "dns_failure",
        "intermittent_outage",
    }

    def test_all_required_categories_present(self, suite: BenchmarkSuite) -> None:
        present = set(suite.categories)
        missing = self.REQUIRED_CATEGORIES - present
        assert not missing, f"Missing categories: {missing}"

    def test_suite_has_dangerous_incidents(self, suite: BenchmarkSuite) -> None:
        dangerous = suite.dangerous_incidents()
        assert len(dangerous) >= 5, f"Expected >= 5 DANGEROUS incidents, got {len(dangerous)}"

    def test_suite_has_hallucinated_incidents(self, suite: BenchmarkSuite) -> None:
        hallucinated = suite.hallucinated_incidents()
        assert (
            len(hallucinated) >= 2
        ), f"Expected >= 2 HALLUCINATED incidents, got {len(hallucinated)}"

    def test_suite_has_false_positives(self, suite: BenchmarkSuite) -> None:
        fp = suite.false_positives()
        assert len(fp) >= 5, f"Expected >= 5 false positive incidents, got {len(fp)}"

    def test_suite_has_escalation_incidents(self, suite: BenchmarkSuite) -> None:
        escalations = suite.requires_escalation_incidents()
        assert len(escalations) >= 10

    def test_suite_has_low_confidence_incidents(self, suite: BenchmarkSuite) -> None:
        low_conf = suite.low_confidence_incidents()
        assert len(low_conf) >= 5

    def test_each_category_has_multiple_incidents(self, suite: BenchmarkSuite) -> None:
        for category in self.REQUIRED_CATEGORIES:
            incidents = suite.by_category(category)
            assert (
                len(incidents) >= 4
            ), f"Category '{category}' has only {len(incidents)} incidents (need >= 4)"

    def test_runner_format_compatibility(self, suite: BenchmarkSuite) -> None:
        for inc in suite.incidents[:5]:
            fmt = inc.to_runner_format()
            assert "name" in fmt
            assert "alert_payload" in fmt
            assert "mocked_tool_responses" in fmt
            assert "golden_classification" in fmt
