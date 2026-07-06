"""Tests for operational readiness validation."""

from runtime.readiness.degraded_mode import DegradedModeVerifier
from runtime.readiness.dependency_validator import OperationalDependencyValidator
from runtime.readiness.deployment_readiness import (
    DeploymentReadinessValidator,
    ReadinessLevel,
)

# ---------------------------------------------------------------------------
# DeploymentReadinessValidator
# ---------------------------------------------------------------------------


class TestDeploymentReadinessValidator:
    def _minimal_profile(self) -> dict:
        return {
            "unit_tests": True,
            "basic_logging": True,
            "test_pass_rate": 0.95,
        }

    def _staging_profile(self) -> dict:
        return {
            "unit_tests": True,
            "integration_tests": True,
            "basic_logging": True,
            "error_handling": True,
            "test_pass_rate": 0.92,
        }

    def _production_profile(self) -> dict:
        return {
            "unit_tests": True,
            "integration_tests": True,
            "load_tests": True,
            "basic_logging": True,
            "structured_logging": True,
            "error_handling": True,
            "circuit_breakers": True,
            "health_checks": True,
            "test_pass_rate": 0.97,
            "reproducibility_validation": True,
            "adversarial_evaluation": True,
            "human_override_documented": True,
        }

    def test_experimental_level_minimal_profile(self):
        validator = DeploymentReadinessValidator()
        report = validator.assess(self._minimal_profile())
        assert report.level == ReadinessLevel.EXPERIMENTAL

    def test_staging_level(self):
        validator = DeploymentReadinessValidator()
        report = validator.assess(self._staging_profile())
        assert report.level == ReadinessLevel.STAGING_CAPABLE

    def test_production_level(self):
        validator = DeploymentReadinessValidator()
        report = validator.assess(self._production_profile())
        assert report.level in (
            ReadinessLevel.PRODUCTION_CAPABLE,
            ReadinessLevel.HIGH_RISK_PRODUCTION,
        )

    def test_autonomy_not_permitted_at_experimental(self):
        validator = DeploymentReadinessValidator()
        report = validator.assess(self._minimal_profile())
        assert report.autonomy_permitted is False

    def test_autonomy_not_permitted_at_staging(self):
        validator = DeploymentReadinessValidator()
        report = validator.assess(self._staging_profile())
        assert report.autonomy_permitted is False

    def test_caveats_include_simulation_warning_at_experimental(self):
        validator = DeploymentReadinessValidator()
        report = validator.assess(self._minimal_profile())
        caveat_text = " ".join(report.caveats).lower()
        assert "simulation" in caveat_text or "synthetic" in caveat_text

    def test_report_to_dict_serializable(self):
        import json

        validator = DeploymentReadinessValidator()
        report = validator.assess(self._minimal_profile())
        json.dumps(report.to_dict())

    def test_empty_profile_gives_experimental(self):
        validator = DeploymentReadinessValidator()
        report = validator.assess({})
        assert report.level == ReadinessLevel.EXPERIMENTAL

    def test_low_pass_rate_prevents_staging(self):
        validator = DeploymentReadinessValidator()
        profile = {
            "unit_tests": True,
            "integration_tests": True,
            "basic_logging": True,
            "error_handling": True,
            "test_pass_rate": 0.70,  # below 90%
        }
        report = validator.assess(profile)
        assert report.level == ReadinessLevel.EXPERIMENTAL

    def test_summary_contains_level(self):
        validator = DeploymentReadinessValidator()
        report = validator.assess(self._minimal_profile())
        assert "Experimental" in report.summary


# ---------------------------------------------------------------------------
# OperationalDependencyValidator
# ---------------------------------------------------------------------------


class TestOperationalDependencyValidator:
    def test_validate_from_imports_returns_report(self):
        validator = OperationalDependencyValidator()
        report = validator.validate_from_imports()
        assert isinstance(report.statuses, list)
        assert isinstance(report.all_required_available, bool)

    def test_validate_known_installed_package(self):
        validator = OperationalDependencyValidator()
        report = validator.validate([{"name": "pytest", "required": False}])
        pytest_status = next((s for s in report.statuses if s.name == "pytest"), None)
        assert pytest_status is not None
        assert pytest_status.available is True

    def test_validate_missing_package(self):
        validator = OperationalDependencyValidator()
        report = validator.validate(
            [{"name": "definitely_not_installed_xyz_abc_123", "required": True}]
        )
        assert not report.all_required_available
        assert "definitely_not_installed_xyz_abc_123" in report.failed_required

    def test_report_serializable(self):
        import json

        validator = OperationalDependencyValidator()
        report = validator.validate_from_imports()
        json.dumps(report.to_dict())


# ---------------------------------------------------------------------------
# DegradedModeVerifier
# ---------------------------------------------------------------------------


class TestDegradedModeVerifier:
    def _full_profile(self) -> dict:
        return {
            "uncertainty_mode": True,
            "llm_fallback": True,
            "replay_integrity_checks": True,
            "circuit_breakers": True,
            "memory_fallback": True,
            "async_resilience": True,
            "failover_documented": True,
        }

    def _empty_profile(self) -> dict:
        return {}

    def test_full_profile_survives_all(self):
        verifier = DegradedModeVerifier()
        report = verifier.verify(self._full_profile())
        assert report.overall_survivability == 1.0
        assert report.telemetry_survivable is True
        assert report.llm_fallback_active is True

    def test_empty_profile_survives_none(self):
        verifier = DegradedModeVerifier()
        report = verifier.verify(self._empty_profile())
        assert report.overall_survivability == 0.0
        assert report.telemetry_survivable is False
        assert report.llm_fallback_active is False

    def test_partial_profile_partial_survivability(self):
        verifier = DegradedModeVerifier()
        profile = {"uncertainty_mode": True, "llm_fallback": True}
        report = verifier.verify(profile)
        assert 0.0 < report.overall_survivability < 1.0

    def test_scenarios_have_expected_fields(self):
        verifier = DegradedModeVerifier()
        report = verifier.verify(self._full_profile())
        for s in report.degradation_scenarios:
            assert "scenario" in s
            assert "survived" in s
            assert "estimated_recovery_seconds" in s

    def test_report_serializable(self):
        import json

        verifier = DegradedModeVerifier()
        report = verifier.verify(self._full_profile())
        json.dumps(report.to_dict())

    def test_recommendation_present(self):
        verifier = DegradedModeVerifier()
        report = verifier.verify(self._full_profile())
        assert len(report.recommendation) > 10
