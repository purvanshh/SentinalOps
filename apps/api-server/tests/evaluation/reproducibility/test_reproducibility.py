"""Tests for evaluation reproducibility framework."""

from evaluation.reproducibility.dataset_fingerprint import DatasetFingerprint
from evaluation.reproducibility.deterministic_runtime import DeterministicRuntime
from evaluation.reproducibility.environment_validator import EnvironmentValidator
from evaluation.reproducibility.replay_consistency import ReplayConsistencyChecker
from evaluation.reproducibility.replay_manifest import ReplayManifest

# ---------------------------------------------------------------------------
# Dataset fingerprint
# ---------------------------------------------------------------------------


class TestDatasetFingerprint:
    def _sample_dataset(self) -> list[dict]:
        return [
            {"incident_id": f"inc-{i}", "severity": "high", "label": "deployment_regression"}
            for i in range(20)
        ]

    def test_compute_returns_fingerprint(self):
        fp = DatasetFingerprint()
        record = fp.compute(self._sample_dataset())
        assert len(record.checksum) == 16
        assert record.item_count == 20
        assert record.label_distribution == {"deployment_regression": 20}

    def test_identical_datasets_produce_same_fingerprint(self):
        fp = DatasetFingerprint()
        ds = self._sample_dataset()
        r1 = fp.compute(ds)
        r2 = fp.compute(list(reversed(ds)))  # order-independent
        assert r1.checksum == r2.checksum

    def test_mutated_dataset_changes_fingerprint(self):
        fp = DatasetFingerprint()
        ds = self._sample_dataset()
        r1 = fp.compute(ds)
        ds[0]["severity"] = "critical"
        r2 = fp.compute(ds)
        assert r1.checksum != r2.checksum

    def test_compare_clean_when_identical(self):
        fp = DatasetFingerprint()
        ds = self._sample_dataset()
        r1 = fp.compute(ds)
        r2 = fp.compute(ds)
        result = fp.compare(r1, r2)
        assert result["clean"] is True
        assert result["mutations"] == []

    def test_compare_detects_item_count_change(self):
        fp = DatasetFingerprint()
        ds = self._sample_dataset()
        r1 = fp.compute(ds)
        r2 = fp.compute(ds[:-1])
        result = fp.compare(r1, r2)
        assert not result["clean"]
        assert any("item_count" in m for m in result["mutations"])

    def test_detect_label_leakage_not_suspicious_small_set(self):
        fp = DatasetFingerprint()
        preds = [{"incident_id": str(i), "prediction": "a"} for i in range(5)]
        golden = [{"incident_id": str(i), "label": "a"} for i in range(5)]
        result = fp.detect_label_leakage(preds, golden, prediction_field="prediction")
        assert not result["suspicious_leakage"]

    def test_detect_label_leakage_suspicious_large_set(self):
        fp = DatasetFingerprint()
        preds = [{"incident_id": str(i), "prediction": "a"} for i in range(30)]
        golden = [{"incident_id": str(i), "label": "a"} for i in range(30)]
        result = fp.detect_label_leakage(preds, golden, prediction_field="prediction")
        assert result["suspicious_leakage"]
        assert result["match_rate"] == 1.0

    def test_no_leakage_when_predictions_differ(self):
        fp = DatasetFingerprint()
        preds = [{"incident_id": str(i), "prediction": "b"} for i in range(30)]
        golden = [{"incident_id": str(i), "label": "a"} for i in range(30)]
        result = fp.detect_label_leakage(preds, golden, prediction_field="prediction")
        assert not result["suspicious_leakage"]
        assert result["match_rate"] == 0.0


# ---------------------------------------------------------------------------
# Deterministic runtime
# ---------------------------------------------------------------------------


class TestDeterministicRuntime:
    def test_same_seed_produces_same_random(self):
        runtime = DeterministicRuntime(seed=99)
        import random

        with runtime.deterministic_context("run-a"):
            vals_a = [random.random() for _ in range(10)]
        with runtime.deterministic_context("run-a"):
            vals_b = [random.random() for _ in range(10)]
        assert vals_a == vals_b

    def test_different_run_ids_produce_different_sequences(self):
        runtime = DeterministicRuntime(seed=42)
        import random

        with runtime.deterministic_context("run-x"):
            vals_x = [random.random() for _ in range(5)]
        with runtime.deterministic_context("run-y"):
            vals_y = [random.random() for _ in range(5)]
        # Different run IDs derive different seeds
        assert vals_x != vals_y

    def test_verify_no_hidden_randomness_identical(self):
        runtime = DeterministicRuntime()
        result = runtime.verify_no_hidden_randomness({"score": 0.5}, {"score": 0.5})
        assert result["deterministic"] is True

    def test_verify_no_hidden_randomness_different(self):
        runtime = DeterministicRuntime()
        result = runtime.verify_no_hidden_randomness({"score": 0.5}, {"score": 0.6})
        assert result["deterministic"] is False
        assert result["hidden_randomness_detected"] is True

    def test_detect_time_dependency_stable(self):
        runtime = DeterministicRuntime()
        results = [{"value": 42} for _ in range(5)]
        r = runtime.detect_time_dependency(results)
        assert r["deterministic"] is True
        assert r["unique_outputs"] == 1

    def test_detect_time_dependency_unstable(self):
        runtime = DeterministicRuntime()
        results = [{"value": i} for i in range(5)]
        r = runtime.detect_time_dependency(results)
        assert r["unique_outputs"] > 1
        assert r["time_dependency_suspected"] is True


# ---------------------------------------------------------------------------
# Environment validator
# ---------------------------------------------------------------------------


class TestEnvironmentValidator:
    def test_snapshot_returns_report(self):
        ev = EnvironmentValidator()
        report = ev.snapshot()
        assert report.python_version
        assert report.environment_hash
        assert isinstance(report.package_versions, dict)

    def test_same_snapshot_produces_same_hash(self):
        ev = EnvironmentValidator()
        r1 = ev.snapshot()
        r2 = ev.snapshot()
        assert r1.environment_hash == r2.environment_hash

    def test_compare_identical_environments_clean(self):
        ev = EnvironmentValidator()
        r = ev.snapshot()
        result = ev.compare(r, r)
        assert result["clean"] is True
        assert result["hash_match"] is True

    def test_compare_detects_python_version_change(self):
        ev = EnvironmentValidator()
        r1 = ev.snapshot()
        import dataclasses

        r2 = dataclasses.replace(r1, python_version="3.8.0")
        result = ev.compare(r1, r2)
        assert not result["clean"]
        assert any("python_version" in w for w in result["all_warnings"])

    def test_installed_versions_is_dict_of_strings(self):
        ev = EnvironmentValidator()
        versions = ev._installed_versions()
        assert isinstance(versions, dict)
        for k, v in list(versions.items())[:5]:
            assert isinstance(k, str)
            assert isinstance(v, str)


# ---------------------------------------------------------------------------
# Replay consistency
# ---------------------------------------------------------------------------


class TestReplayConsistencyChecker:
    def test_identical_results_are_consistent(self):
        checker = ReplayConsistencyChecker()
        baseline = {"accuracy": 0.85, "f1": 0.80}
        result = checker.check(baseline, baseline)
        assert result.consistent is True
        assert result.drift_score == 0.0

    def test_minor_drift_within_tolerance(self):
        checker = ReplayConsistencyChecker()
        baseline = {"accuracy": 0.85}
        current = {"accuracy": 0.86}
        result = checker.check(baseline, current, tolerance=0.02)
        assert result.consistent is True

    def test_large_drift_flags_inconsistency(self):
        checker = ReplayConsistencyChecker()
        baseline = {"accuracy": 0.50}
        current = {"accuracy": 0.95}
        result = checker.check(baseline, current, tolerance=0.02)
        assert not result.consistent
        assert result.drift_score > 0.10

    def test_contamination_detected_when_scores_inflate(self):
        checker = ReplayConsistencyChecker()
        baseline = {"accuracy": 0.50, "f1": 0.48, "precision": 0.49}
        current = {"accuracy": 0.90, "f1": 0.88, "precision": 0.89}
        result = checker.check(baseline, current)
        assert "suspicious_score_inflation" in result.contamination_flags

    def test_schema_change_detected(self):
        checker = ReplayConsistencyChecker()
        baseline = {"accuracy": 0.85, "f1": 0.80}
        current = {"accuracy": 0.85, "new_metric": 0.75}
        result = checker.check(baseline, current)
        assert "structural_schema_change" in result.contamination_flags

    def test_same_seed_instability_detected(self):
        checker = ReplayConsistencyChecker()
        run_a = {"accuracy": 0.85}
        run_b = {"accuracy": 0.70}
        result = checker.check_seed_stability(run_a, run_b, seed_a=42, seed_b=42)
        assert result["same_seed"] is True
        assert result["seed_drift_violation"] is True


# ---------------------------------------------------------------------------
# Replay manifest
# ---------------------------------------------------------------------------


class TestReplayManifest:
    def test_record_and_verify(self):
        manifest = ReplayManifest()
        entry = manifest.record(
            run_id="run-001",
            benchmark_version="v1.0",
            dataset_checksum="abc123",
            environment_hash="def456",
            seed=42,
            parameters={"threshold": 0.5},
            results={"accuracy": 0.85},
            passed=True,
        )
        assert entry.run_id == "run-001"
        assert manifest.verify("run-001", {"accuracy": 0.85}) is True

    def test_verify_fails_on_different_results(self):
        manifest = ReplayManifest()
        manifest.record(
            run_id="run-002",
            benchmark_version="v1.0",
            dataset_checksum="abc",
            environment_hash="def",
            seed=42,
            parameters={},
            results={"accuracy": 0.85},
            passed=True,
        )
        assert manifest.verify("run-002", {"accuracy": 0.90}) is False

    def test_detect_drift_no_drift(self):
        manifest = ReplayManifest()
        manifest.record(
            run_id="run-003",
            benchmark_version="v1.0",
            dataset_checksum="checksum-stable",
            environment_hash="hash",
            seed=1,
            parameters={},
            results={},
            passed=True,
        )
        assert manifest.detect_drift("run-003", "checksum-stable") is False

    def test_detect_drift_mutated_dataset(self):
        manifest = ReplayManifest()
        manifest.record(
            run_id="run-004",
            benchmark_version="v1.0",
            dataset_checksum="original",
            environment_hash="hash",
            seed=1,
            parameters={},
            results={},
            passed=True,
        )
        assert manifest.detect_drift("run-004", "mutated") is True

    def test_summary_pass_rate(self):
        manifest = ReplayManifest()
        for i in range(10):
            manifest.record(
                run_id=f"r{i}",
                benchmark_version="v1",
                dataset_checksum="c",
                environment_hash="h",
                seed=i,
                parameters={},
                results={},
                passed=(i % 2 == 0),
            )
        s = manifest.summary()
        assert s["total_runs"] == 10
        assert s["passed"] == 5
        assert s["pass_rate"] == 0.5

    def test_unknown_run_verify_returns_false(self):
        manifest = ReplayManifest()
        assert manifest.verify("nonexistent", {}) is False

    def test_unknown_run_drift_returns_true(self):
        manifest = ReplayManifest()
        assert manifest.detect_drift("nonexistent", "any") is True
