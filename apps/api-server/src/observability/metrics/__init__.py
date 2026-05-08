from prometheus_client import Counter

API_REQUEST_COUNT = Counter("api_requests_total", "Total API requests handled by SentinelOps")


def build_metrics_snapshot() -> dict[str, float]:
    return {
        "api_requests_total": float(API_REQUEST_COUNT._value.get()),  # noqa: SLF001
    }
