# SentinelOps Architecture Overview

SentinelOps AI is organized around a FastAPI control plane, a checkpoint-backed workflow graph, and a Next.js dashboard.

## Runtime layers

- API layer: incident intake, approval APIs, graph start/resume routes, evaluation summary routes
- Workflow layer: router, evidence gatherers, root cause, risk, remediation, approval, execution, and postmortem nodes
- Persistence layer: PostgreSQL-backed incidents, checkpoints, postmortems, remediation history, and prevention items
- Observability layer: Prometheus metrics, Grafana dashboards, structured JSON logs, and workflow callback hooks
- Frontend layer: incident board, approval center, graph view, and evaluation dashboard

## Delivery model

- Local: `docker-compose.yml`
- PaaS blueprint: [infrastructure/render.yaml](/Users/purvansh/Desktop/Projects/SentinalOps/infrastructure/render.yaml:1)
- CI: evaluation and deploy GitHub workflows
