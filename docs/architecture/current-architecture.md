# Current Architecture

SentinelOps currently runs as a FastAPI control plane backed by PostgreSQL, Redis, Qdrant, Celery, Prometheus, Loki, Grafana, and Tempo in local Docker Compose.

## Runtime shape

1. `POST /incidents/webhook` creates an incident record.
2. A Celery task or manual graph start triggers the orchestration flow.
3. The workflow graph executes router, metrics, logs, deployment, root cause, risk, remediation, approval, execution, and postmortem stages.
4. Agent executions, evidence items, checkpoints, approvals, and postmortems are persisted to PostgreSQL.
5. Active incident state is cached in Redis and graph state can be streamed over WebSocket.
6. Static knowledge retrieval uses Qdrant-backed collections for patterns, past incidents, runbooks, and prevention items.

## Supporting systems

- Next.js dashboard for incidents, approvals, traces, and evaluations
- Simulation stack for payment, auth, gateway, and notification mock services
- Prometheus, Grafana, Loki, and Tempo for platform observability

## Honest limitations

- The graph is LangGraph-backed but still lightly validated in real runtime conditions.
- Several external integrations remain stubs rather than production connectors.
- CI and packaging are now present, but they still need live execution against the full stack.
