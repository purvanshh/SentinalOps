import json


def generate_db_latency_incident() -> dict[str, object]:
    return {
        "name": "db_latency",
        "service": "payment-api",
        "description": "Database latency cascades into payment API request timeouts.",
        "webhook": {
            "title": "Payment database latency exceeded threshold",
            "summary": "DB p99 latency crossed 900ms and connection pool saturation followed.",
            "severity": "critical",
            "source": "prometheus",
            "labels": {"service": "payment-api"},
        },
    }


if __name__ == "__main__":
    print(json.dumps(generate_db_latency_incident(), indent=2))
