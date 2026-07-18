from __future__ import annotations

from typing import Any, Dict


class ExpectationLibrary:
    """Library containing expected telemetry signatures and symptoms for failure mechanisms."""

    def __init__(self) -> None:
        self.expectations: Dict[str, Dict[str, Any]] = {
            "deployment_error": {
                "required_node_types": {"deployment", "metric_anomaly"},
                "expected_keywords": ["deploy", "rollback", "upgrade", "regression"],
            },
            "resource_exhaustion": {
                "required_node_types": {"metric_anomaly"},
                "expected_keywords": [
                    "cpu", "memory", "exhausted", "starvation",
                    "limit", "oom", "leak",
                ],
            },
            "cascade_failure": {
                "required_node_types": {"metric_anomaly", "topology"},
                "expected_keywords": ["dependency", "cascade", "propagate", "timeout", "retry"],
            },
            "configuration_drift": {
                "required_node_types": {"deployment"},
                "expected_keywords": ["config", "parameter", "tuning", "env", "settings"],
            },
            "dependency_failure": {
                "required_node_types": {"log_error"},
                "expected_keywords": [
                    "timeout", "connection refused", "502", "503", "504",
                    "http", "api",
                ],
            },
        }

    def get_expectations(self, mechanism_type: str) -> dict[str, Any] | None:
        return self.expectations.get(mechanism_type)
