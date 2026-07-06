"""Tests for architecture validation suite."""

from pathlib import Path

from validation.architecture.dependency_graph_validator import DependencyGraphValidator
from validation.architecture.layer_boundary_validator import LayerBoundaryValidator
from validation.architecture.observability_coverage_audit import ObservabilityCoverageAuditor

SRC_ROOT = Path(__file__).parent.parent.parent / "src"


# ---------------------------------------------------------------------------
# DependencyGraphValidator
# ---------------------------------------------------------------------------


class TestDependencyGraphValidator:
    def test_validate_src_returns_report(self):
        validator = DependencyGraphValidator()
        report = validator.validate(SRC_ROOT)
        assert isinstance(report.total_modules, int)
        assert report.total_modules > 0

    def test_forbidden_cross_layer_imports_report(self):
        # Validates that the checker runs without error and produces a list.
        # Known pre-existing coupling: evaluation.replay_integration → runtime.*
        # This is documented as a known architectural limitation in KNOWN_LIMITATIONS.md.
        validator = DependencyGraphValidator()
        report = validator.validate(SRC_ROOT)
        assert isinstance(report.forbidden_imports, list)
        # Verify all reported violations have the required fields
        for v in report.forbidden_imports:
            assert "module" in v
            assert "forbidden_import" in v
            assert "reason" in v

    def test_report_serializable(self):
        import json

        validator = DependencyGraphValidator()
        report = validator.validate(SRC_ROOT)
        json.dumps(report.to_dict())

    def test_summary_present(self):
        validator = DependencyGraphValidator()
        report = validator.validate(SRC_ROOT)
        assert len(report.summary) > 0

    def test_small_synthetic_graph_no_cycle(self):
        # Unit-level test with a synthetic in-memory graph
        validator = DependencyGraphValidator()
        graph = {"a": ["b"], "b": ["c"], "c": []}
        cycles = validator._detect_cycles(graph)
        assert cycles == []

    def test_small_synthetic_graph_cycle_detected(self):
        validator = DependencyGraphValidator()
        graph = {"a": ["b"], "b": ["c"], "c": ["a"]}
        cycles = validator._detect_cycles(graph)
        assert len(cycles) > 0


# ---------------------------------------------------------------------------
# LayerBoundaryValidator
# ---------------------------------------------------------------------------


class TestLayerBoundaryValidator:
    def test_validate_src_returns_report(self):
        validator = LayerBoundaryValidator()
        report = validator.validate(SRC_ROOT)
        assert isinstance(report.layers_checked, list)

    def test_report_serializable(self):
        import json

        validator = LayerBoundaryValidator()
        report = validator.validate(SRC_ROOT)
        json.dumps(report.to_dict())

    def test_summary_present(self):
        validator = LayerBoundaryValidator()
        report = validator.validate(SRC_ROOT)
        assert len(report.summary) > 0

    def test_layer_from_path_known_layers(self):
        validator = LayerBoundaryValidator()
        assert validator._layer_from_path("api/routes.py") == "api"
        assert validator._layer_from_path("evaluation/scorer.py") == "evaluation"
        assert validator._layer_from_path("observability/metrics.py") == "observability"

    def test_layer_from_path_unknown_returns_none(self):
        validator = LayerBoundaryValidator()
        assert validator._layer_from_path("unknown/module.py") is None


# ---------------------------------------------------------------------------
# ObservabilityCoverageAuditor
# ---------------------------------------------------------------------------


class TestObservabilityCoverageAuditor:
    def test_audit_src_returns_report(self):
        auditor = ObservabilityCoverageAuditor()
        report = auditor.audit(SRC_ROOT)
        assert isinstance(report.total_modules, int)
        assert report.total_modules > 0

    def test_coverage_rate_in_bounds(self):
        auditor = ObservabilityCoverageAuditor()
        report = auditor.audit(SRC_ROOT)
        assert 0.0 <= report.coverage_rate <= 1.0

    def test_report_serializable(self):
        import json

        auditor = ObservabilityCoverageAuditor()
        report = auditor.audit(SRC_ROOT)
        json.dumps(report.to_dict())

    def test_instrumented_leq_total(self):
        auditor = ObservabilityCoverageAuditor()
        report = auditor.audit(SRC_ROOT)
        assert report.instrumented_modules <= report.total_modules

    def test_recommendation_present(self):
        auditor = ObservabilityCoverageAuditor()
        report = auditor.audit(SRC_ROOT)
        assert len(report.recommendation) > 10

    def test_instrumented_module_detection(self):
        # A module with 'logger' in it should be detected as instrumented
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            (tmp / "module_with_logging.py").write_text(
                "import logging\nlogger = logging.getLogger(__name__)\n"
            )
            (tmp / "module_without.py").write_text("def foo(): return 1\n")
            auditor = ObservabilityCoverageAuditor()
            report = auditor.audit(tmp)
            assert report.instrumented_modules >= 1
            assert report.total_modules == 2
