import json


def generate_bad_deployment_event() -> dict[str, object]:
    return {
        "deployment": {
            "deployment_id": "DEP-4351",
            "service": "payment-api",
            "version": "v2.3.1",
            "time": "2026-05-08T14:02:55Z",
            "repo": "sentinelops/payment-api",
            "commit_sha": "abc123def456",
            "change_type": "backend",
            "summary": "Refactored connection pool from HikariCP to custom pool",
        },
        "incident_webhook": {
            "title": "Payment API latency exceeded threshold",
            "summary": "Latency crossed p99 threshold after deployment.",
            "severity": "high",
            "source": "prometheus",
            "labels": {"service": "payment-api"},
        },
    }


if __name__ == "__main__":
    print(json.dumps(generate_bad_deployment_event(), indent=2))
