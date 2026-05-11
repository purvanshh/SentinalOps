# ADR 0004: Local Runtime Stack

## Status

Accepted

## Context

The platform needs a realistic local environment that includes orchestration, state, telemetry, tracing, and simulation services so that architecture claims can be exercised outside unit tests.

## Decision

Use Docker Compose as the primary local runtime with:

- API server
- Celery worker and beat
- PostgreSQL
- Redis
- Qdrant
- Prometheus
- Grafana
- Loki
- Tempo
- Next.js dashboard
- optional simulation services via a dedicated simulation compose file

## Consequences

- Local startup is heavier, but the system becomes much more representative.
- Service health checks and ordering reduce confusing boot-time failure modes.
