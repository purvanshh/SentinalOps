import json


def generate_cpu_spike_incident() -> dict[str, object]:
    return {
        "name": "cpu_spike",
        "service": "gateway-service",
        "description": "Gateway CPU spikes and begins returning upstream timeout errors.",
        "webhook": {
            "title": "Gateway CPU usage exceeded threshold",
            "summary": "Gateway CPU crossed 95% and error rate increased.",
            "severity": "high",
            "source": "prometheus",
            "labels": {"service": "gateway-service"},
        },
    }


if __name__ == "__main__":
    print(json.dumps(generate_cpu_spike_incident(), indent=2))
