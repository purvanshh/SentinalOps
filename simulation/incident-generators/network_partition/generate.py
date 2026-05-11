import json


def generate_network_partition_incident(scenario: str = "gateway-to-payment") -> dict[str, object]:
    return {
        "name": "network_partition",
        "scenario": scenario,
        "service": "gateway-service",
        "description": "Synthetic network partition between gateway-service and payment-api.",
        "webhook": {
            "title": "Gateway upstream connectivity degraded",
            "summary": f"Synthetic network partition triggered for scenario {scenario}.",
            "severity": "critical",
            "source": "prometheus",
            "labels": {"service": "gateway-service"},
        },
    }


if __name__ == "__main__":
    print(json.dumps(generate_network_partition_incident(), indent=2))
