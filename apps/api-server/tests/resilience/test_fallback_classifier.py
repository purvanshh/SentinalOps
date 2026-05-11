"""
Tests for the deterministic fallback classifier.

Verifies that the classifier correctly categorizes incidents
using only keyword/pattern matching with zero external dependencies.
"""

import pytest

from core.resilience.fallback_classifier import DeterministicFallbackClassifier, FallbackClassification


@pytest.fixture
def classifier():
    return DeterministicFallbackClassifier()


class TestDeterministicFallbackClassifier:
    """Test the deterministic fallback classifier."""

    def test_latency_classification(self, classifier: DeterministicFallbackClassifier):
        payload = {
            "title": "High latency on payment service",
            "summary": "P99 latency spike detected, response time exceeded 5s threshold",
            "severity": "high",
        }
        result = classifier.classify(payload)
        assert isinstance(result, FallbackClassification)
        assert result.incident_type == "latency"
        assert result.fallback is True
        assert result.provider_used == "deterministic_fallback"
        assert result.confidence > 0.0
        assert result.severity == "high"

    def test_cpu_classification(self, classifier: DeterministicFallbackClassifier):
        payload = {
            "title": "CPU usage critical on worker nodes",
            "summary": "CPU utilization above 95% on all worker pods, load average high",
            "severity": "critical",
        }
        result = classifier.classify(payload)
        assert result.incident_type == "cpu"
        assert result.severity == "critical"
        assert result.requires_immediate_investigation is True

    def test_memory_classification(self, classifier: DeterministicFallbackClassifier):
        payload = {
            "title": "OOM killed container in production",
            "summary": "Memory pressure detected, container oom killed, heap exhausted",
            "severity": "high",
        }
        result = classifier.classify(payload)
        assert result.incident_type == "memory"
        assert result.confidence > 0.3

    def test_deployment_classification(self, classifier: DeterministicFallbackClassifier):
        payload = {
            "title": "Errors after deployment of v2.3.1",
            "summary": "5xx errors spiked after deploy, possible regression in new version",
            "severity": "high",
        }
        result = classifier.classify(payload)
        assert result.incident_type == "deployment"

    def test_database_classification(self, classifier: DeterministicFallbackClassifier):
        payload = {
            "title": "Database connection pool exhausted",
            "summary": "PostgreSQL connection pool full, slow queries detected, deadlock warnings",
            "severity": "high",
        }
        result = classifier.classify(payload)
        assert result.incident_type == "database"

    def test_networking_classification(self, classifier: DeterministicFallbackClassifier):
        payload = {
            "title": "DNS resolution failures",
            "summary": "Network connectivity issues, DNS lookup timeout, 503 service unavailable",
            "severity": "medium",
        }
        result = classifier.classify(payload)
        assert result.incident_type == "networking"

    def test_unknown_classification(self, classifier: DeterministicFallbackClassifier):
        payload = {
            "title": "Something happened",
            "summary": "An alert was triggered",
            "severity": "low",
        }
        result = classifier.classify(payload)
        assert result.incident_type == "unknown"
        assert result.recommended_workflow == "human_triage"
        assert result.confidence <= 0.2

    def test_empty_payload(self, classifier: DeterministicFallbackClassifier):
        result = classifier.classify({})
        assert result.incident_type == "unknown"
        assert result.fallback is True

    def test_labels_and_annotations_searched(self, classifier: DeterministicFallbackClassifier):
        payload = {
            "title": "Alert fired",
            "summary": "Check system",
            "labels": {"alertname": "HighLatency", "service": "api-gateway"},
            "annotations": {"description": "P99 latency spike on api-gateway"},
        }
        result = classifier.classify(payload)
        assert result.incident_type == "latency"

    def test_severity_from_payload(self, classifier: DeterministicFallbackClassifier):
        payload = {
            "title": "High CPU usage",
            "summary": "CPU utilization high",
            "severity": "critical",
        }
        result = classifier.classify(payload)
        assert result.severity == "critical"

    def test_deterministic_same_input_same_output(self, classifier: DeterministicFallbackClassifier):
        payload = {
            "title": "Database connection timeout",
            "summary": "Connection pool exhausted",
            "severity": "high",
        }
        result1 = classifier.classify(payload)
        result2 = classifier.classify(payload)
        assert result1.incident_type == result2.incident_type
        assert result1.confidence == result2.confidence
        assert result1.severity == result2.severity
