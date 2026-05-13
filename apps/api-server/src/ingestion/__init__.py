"""
Telemetry Ingestion module for SentinelOps Phase 47.

Normalizes heterogeneous telemetry from multiple sources:
  telemetry_normalizer   — TelemetryNormalizer + UnifiedTelemetryEvent
  event_adapters/        — Source-specific payload adapters
    prometheus_adapter   — Prometheus alerts and metrics
    loki_adapter         — Loki log streams
    github_adapter       — GitHub deployments and workflow runs
    kubernetes_adapter   — Kubernetes events and pod phases
"""
