"""Tests for telemetry normalization and ingestion adapters (Phase 47)."""

from __future__ import annotations

from ingestion.event_adapters import (
    github_adapter,
    kubernetes_adapter,
    loki_adapter,
    prometheus_adapter,
)
from ingestion.telemetry_normalizer import (
    TelemetryNormalizer,
    normalize_service,
    normalize_severity,
    normalize_timestamp,
)

# ---------------------------------------------------------------------------
# normalize_severity
# ---------------------------------------------------------------------------


class TestNormalizeSeverity:
    def test_critical_variants(self):
        for raw in ("critical", "CRITICAL", "crit", "fatal", "alert", "emerg"):
            assert normalize_severity(raw) == "critical"

    def test_error_variants(self):
        for raw in ("error", "ERROR", "err"):
            assert normalize_severity(raw) == "error"

    def test_warning_variants(self):
        for raw in ("warning", "warn", "WARNING"):
            assert normalize_severity(raw) == "warning"

    def test_info_variants(self):
        for raw in ("info", "notice", "informational", "INFO"):
            assert normalize_severity(raw) == "info"

    def test_debug_variants(self):
        for raw in ("debug", "trace"):
            assert normalize_severity(raw) == "debug"

    def test_unknown_falls_back_to_info(self):
        assert normalize_severity("completely_unknown") == "info"

    def test_empty_string_is_info(self):
        assert normalize_severity("") == "info"


# ---------------------------------------------------------------------------
# normalize_timestamp
# ---------------------------------------------------------------------------


class TestNormalizeTimestamp:
    def test_iso_z_format(self):
        result = normalize_timestamp("2026-05-01T10:00:00Z")
        assert "2026-05-01" in result

    def test_iso_offset_format(self):
        result = normalize_timestamp("2026-05-01T10:00:00+00:00")
        assert "2026-05-01" in result

    def test_unix_epoch_int(self):
        result = normalize_timestamp(1746050400)
        assert result != ""
        assert "T" in result

    def test_unix_epoch_float(self):
        result = normalize_timestamp(1746050400.0)
        assert result != ""

    def test_empty_returns_empty(self):
        assert normalize_timestamp("") == ""

    def test_none_returns_empty(self):
        assert normalize_timestamp(None) == ""

    def test_garbage_returns_string(self):
        result = normalize_timestamp("not-a-timestamp")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# normalize_service
# ---------------------------------------------------------------------------


class TestNormalizeService:
    def test_strips_deployment_prefix(self):
        assert normalize_service("deployment/my-api") == "my-api"

    def test_strips_service_prefix(self):
        assert normalize_service("service/payment-svc") == "payment-svc"

    def test_strips_pod_prefix(self):
        assert normalize_service("pod/api-pod-abc") == "api-pod-abc"

    def test_lowercases(self):
        assert normalize_service("MyAPI") == "myapi"

    def test_strips_whitespace(self):
        assert normalize_service("  api  ") == "api"

    def test_no_prefix_unchanged(self):
        assert normalize_service("checkout") == "checkout"


# ---------------------------------------------------------------------------
# TelemetryNormalizer
# ---------------------------------------------------------------------------


class TestTelemetryNormalizer:
    def _raw(self, **overrides):
        base = {
            "event_id": "E001",
            "timestamp_iso": "2026-05-01T10:00:00Z",
            "service": "api",
            "severity": "error",
            "message": "something broke",
            "labels": {"env": "prod"},
        }
        base.update(overrides)
        return base

    def test_normalize_basic_event(self):
        normalizer = TelemetryNormalizer()
        result = normalizer.normalize(self._raw(), source_kind="test")
        from ingestion.telemetry_normalizer import UnifiedTelemetryEvent

        assert isinstance(result, UnifiedTelemetryEvent)

    def test_normalize_sets_service(self):
        normalizer = TelemetryNormalizer()
        result = normalizer.normalize(self._raw(service="deployment/checkout"))
        from ingestion.telemetry_normalizer import UnifiedTelemetryEvent

        assert isinstance(result, UnifiedTelemetryEvent)
        assert result.service == "checkout"

    def test_normalize_severity_mapping(self):
        normalizer = TelemetryNormalizer()
        result = normalizer.normalize(self._raw(severity="crit"))
        from ingestion.telemetry_normalizer import UnifiedTelemetryEvent

        assert isinstance(result, UnifiedTelemetryEvent)
        assert result.severity == "critical"

    def test_topology_enrichment(self):
        topology = {"api": ["db", "cache"], "cache": ["redis"]}
        normalizer = TelemetryNormalizer(topology_map=topology)
        result = normalizer.normalize(self._raw(service="api"))
        from ingestion.telemetry_normalizer import UnifiedTelemetryEvent

        assert isinstance(result, UnifiedTelemetryEvent)
        assert "db" in result.downstream_services
        assert result.dependency_count >= 2

    def test_upstream_enrichment(self):
        topology = {"frontend": ["api"], "api": ["db"]}
        normalizer = TelemetryNormalizer(topology_map=topology)
        result = normalizer.normalize(self._raw(service="api"))
        from ingestion.telemetry_normalizer import UnifiedTelemetryEvent

        assert isinstance(result, UnifiedTelemetryEvent)
        assert "frontend" in result.upstream_services

    def test_ingestion_confidence_full(self):
        normalizer = TelemetryNormalizer()
        result = normalizer.normalize(self._raw())
        from ingestion.telemetry_normalizer import UnifiedTelemetryEvent

        assert isinstance(result, UnifiedTelemetryEvent)
        assert result.ingestion_confidence >= 0.80

    def test_ingestion_confidence_partial(self):
        normalizer = TelemetryNormalizer()
        result = normalizer.normalize({"event_id": "E1"})  # minimal
        from ingestion.telemetry_normalizer import UnifiedTelemetryEvent

        assert isinstance(result, UnifiedTelemetryEvent)
        assert result.ingestion_confidence < 0.80

    def test_normalize_batch(self):
        normalizer = TelemetryNormalizer()
        batch = [self._raw(event_id=f"E{i}") for i in range(5)]
        result = normalizer.normalize_batch(batch, source_kind="test")
        assert result.total_attempted == 5
        assert result.success_rate == 1.0

    def test_normalize_batch_quarantines_bad(self):
        normalizer = TelemetryNormalizer()

        class Unserializable:
            pass

        # Pass an object that will cause normalization to fail via bad labels type
        raw = {"event_id": "E1", "labels": "not_a_dict"}
        result = normalizer.normalize_batch([raw])
        # Should handle gracefully — either normalize with empty labels or quarantine
        assert result.total_attempted == 1

    def test_deployment_id_extracted_from_labels(self):
        normalizer = TelemetryNormalizer()
        raw = self._raw(labels={"env": "prod", "deployment_id": "dep-123"})
        result = normalizer.normalize(raw)
        from ingestion.telemetry_normalizer import UnifiedTelemetryEvent

        assert isinstance(result, UnifiedTelemetryEvent)
        assert result.deployment_id == "dep-123"

    def test_fingerprint_stable(self):
        normalizer = TelemetryNormalizer()
        r1 = normalizer.normalize(self._raw())
        r2 = normalizer.normalize(self._raw())
        from ingestion.telemetry_normalizer import UnifiedTelemetryEvent

        assert isinstance(r1, UnifiedTelemetryEvent)
        assert isinstance(r2, UnifiedTelemetryEvent)
        assert r1.fingerprint() == r2.fingerprint()

    def test_mean_confidence_in_result(self):
        normalizer = TelemetryNormalizer()
        batch = [self._raw(event_id=f"E{i}") for i in range(3)]
        result = normalizer.normalize_batch(batch)
        assert result.mean_confidence > 0.0

    def test_fallback_timestamp_field(self):
        normalizer = TelemetryNormalizer()
        raw = {"event_id": "E1", "timestamp": "2026-05-01T10:00:00Z", "service": "api"}
        result = normalizer.normalize(raw)
        from ingestion.telemetry_normalizer import UnifiedTelemetryEvent

        assert isinstance(result, UnifiedTelemetryEvent)
        assert result.timestamp_iso != ""


# ---------------------------------------------------------------------------
# Prometheus adapter
# ---------------------------------------------------------------------------


class TestPrometheusAdapter:
    def test_adapt_alert_basic(self):
        raw = {
            "status": "firing",
            "labels": {"alertname": "HighLatency", "severity": "critical", "job": "api"},
            "annotations": {"description": "p99 > 1s"},
            "startsAt": "2026-05-01T10:00:00Z",
        }
        adapted = prometheus_adapter.adapt_alert(raw)
        assert adapted["kind"] == "alert"
        assert adapted["service"] == "api"
        assert adapted["severity"] == "critical"

    def test_adapt_metric_basic(self):
        raw = {
            "metric": {"__name__": "http_requests_total", "job": "api"},
            "value": [1746050400, "1234"],
        }
        adapted = prometheus_adapter.adapt_metric(raw)
        assert adapted["kind"] == "metric"
        assert adapted["service"] == "api"

    def test_adapt_batch(self):
        alerts = [
            {
                "status": "firing",
                "labels": {"alertname": f"Alert{i}", "job": "svc"},
                "startsAt": "2026-05-01T10:00:00Z",
            }
            for i in range(3)
        ]
        adapted = prometheus_adapter.adapt_batch(alerts)
        assert len(adapted) == 3


# ---------------------------------------------------------------------------
# Loki adapter
# ---------------------------------------------------------------------------


class TestLokiAdapter:
    def test_adapt_stream_entry(self):
        result = loki_adapter.adapt_stream_entry(
            stream_labels={"job": "api", "namespace": "prod"},
            ts_ns="1746050400000000000",
            log_line="ERROR: connection refused",
        )
        assert result["kind"] == "log"
        assert result["service"] == "api"
        assert result["severity"] == "error"

    def test_adapt_query_result(self):
        result_data = {
            "stream": {"job": "checkout", "namespace": "prod"},
            "values": [
                ["1746050400000000000", "ERROR: timeout"],
                ["1746050401000000000", "INFO: retry"],
            ],
        }
        adapted = loki_adapter.adapt_query_result(result_data)
        assert len(adapted) == 2

    def test_severity_heuristic_critical(self):
        result = loki_adapter.adapt_stream_entry(
            {"job": "api"},
            "1746050400000000000",
            "FATAL: out of memory",
        )
        assert result["severity"] == "critical"

    def test_adapt_batch(self):
        streams = [
            {
                "stream": {"job": f"svc{i}"},
                "values": [["1746050400000000000", f"log {i}"]],
            }
            for i in range(3)
        ]
        adapted = loki_adapter.adapt_batch(streams)
        assert len(adapted) == 3


# ---------------------------------------------------------------------------
# GitHub adapter
# ---------------------------------------------------------------------------


class TestGitHubAdapter:
    def test_adapt_deployment(self):
        raw = {
            "deployment": {
                "id": 1,
                "environment": "prod",
                "ref": "main",
                "sha": "abc123def456",
                "created_at": "2026-05-01T10:00:00Z",
            },
            "repository": {"name": "api"},
        }
        adapted = github_adapter.adapt_deployment(raw)
        assert adapted["kind"] == "deployment"
        assert adapted["service"] == "api"

    def test_adapt_deployment_status_failure(self):
        raw = {
            "deployment_status": {
                "id": 2,
                "state": "failure",
                "created_at": "2026-05-01T10:05:00Z",
            },
            "deployment": {"id": 1, "environment": "prod"},
            "repository": {"name": "api"},
        }
        adapted = github_adapter.adapt_deployment_status(raw)
        assert adapted["severity"] == "error"

    def test_adapt_workflow_run(self):
        raw = {
            "workflow_run": {
                "id": 3,
                "name": "CI",
                "head_branch": "main",
                "conclusion": "success",
                "created_at": "2026-05-01T10:00:00Z",
            },
            "repository": {"name": "api"},
        }
        adapted = github_adapter.adapt_workflow_run(raw)
        assert adapted["severity"] == "info"


# ---------------------------------------------------------------------------
# Kubernetes adapter
# ---------------------------------------------------------------------------


class TestKubernetesAdapter:
    def test_adapt_k8s_warning_event(self):
        raw = {
            "type": "Warning",
            "reason": "OOMKilling",
            "message": "pod killed due to OOM",
            "involvedObject": {"kind": "Pod", "name": "api-pod", "namespace": "prod"},
            "firstTimestamp": "2026-05-01T10:00:00Z",
            "lastTimestamp": "2026-05-01T10:01:00Z",
            "count": 3,
            "metadata": {"name": "oom-event-abc"},
        }
        adapted = kubernetes_adapter.adapt_event(raw)
        assert adapted["kind"] == "alert"
        assert adapted["severity"] == "critical"

    def test_adapt_k8s_normal_event(self):
        raw = {
            "type": "Normal",
            "reason": "Started",
            "message": "container started",
            "involvedObject": {"kind": "Pod", "name": "api-pod", "namespace": "prod"},
            "lastTimestamp": "2026-05-01T10:00:00Z",
            "metadata": {"name": "start-event"},
        }
        adapted = kubernetes_adapter.adapt_event(raw)
        assert adapted["kind"] == "log"

    def test_adapt_pod_phase_failed(self):
        raw = {
            "metadata": {"name": "api-pod", "namespace": "prod", "labels": {"app": "api"}},
            "status": {"phase": "Failed", "startTime": "2026-05-01T10:00:00Z"},
        }
        adapted = kubernetes_adapter.adapt_pod_phase(raw)
        assert adapted["severity"] == "error"
        assert adapted["service"] == "api"

    def test_adapt_batch(self):
        events = [
            {
                "type": "Warning",
                "reason": "BackOff",
                "message": "back off restarting",
                "involvedObject": {"kind": "Pod", "name": f"pod-{i}", "namespace": "default"},
                "lastTimestamp": "2026-05-01T10:00:00Z",
                "metadata": {"name": f"event-{i}"},
            }
            for i in range(3)
        ]
        adapted = kubernetes_adapter.adapt_batch(events)
        assert len(adapted) == 3
