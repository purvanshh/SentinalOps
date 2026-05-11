import json


def generate_memory_leak_incident() -> dict[str, object]:
    return {
        "name": "memory_leak",
        "service": "notification-service",
        "description": "Notification workers gradually consume memory and fall behind.",
        "webhook": {
            "title": "Notification service memory usage exceeded threshold",
            "summary": "Heap growth is sustained and queue depth is climbing.",
            "severity": "high",
            "source": "prometheus",
            "labels": {"service": "notification-service"},
        },
    }


if __name__ == "__main__":
    print(json.dumps(generate_memory_leak_incident(), indent=2))
