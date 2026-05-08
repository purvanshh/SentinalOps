# SentinelOps AI

SentinelOps AI is a multi-agent incident investigation and reliability orchestration platform for simulated production incidents. It combines alert ingestion, telemetry gathering, evidence-grounded root-cause analysis, quantitative risk scoring, approval-gated remediation, and postmortem generation in a single developer-friendly monorepo.

The project is modeled after modern AI Ops systems such as PagerDuty AI Ops, Datadog AI Investigations, and Azure Copilot for Operations, but built as an educational and portfolio-grade reference implementation.

## What This Project Tries To Be

- A stateful incident investigation workflow, not a generic chatbot
- A tool-augmented backend that queries metrics, logs, deployment history, and static knowledge sources
- A multi-agent architecture with explicit responsibilities for routing, evidence gathering, reasoning, risk, remediation, and postmortem generation
- A system that demonstrates approval-gated operations, evaluation scaffolding, and observability-aware engineering

## Product Flow

1. A Prometheus-style alert hits the webhook intake API.
2. The Router Agent classifies the incident and selects the investigation path.
3. Metrics, Logs, and Deployment agents gather evidence in parallel.
4. The Root Cause Agent synthesizes evidence into ranked hypotheses with citations.
5. The Risk Agent estimates blast radius and remediation risk.
6. The Remediation Agent proposes actions.
7. The Approval flow pauses risky actions for a human decision.
8. Execution proceeds only after approval.
9. The Postmortem Agent generates an incident report and prevention items.
10. The evaluation layer scores synthetic incidents for quality and regressions.

## Repository Layout

```text
sentinelops-ai/
├── apps/
│   ├── api-server/        # FastAPI backend, agents, orchestration, tools, DB, evals
│   └── web-dashboard/     # Next.js dashboard
├── infrastructure/        # Docker configs, monitoring assets, deployment manifests
├── simulation/            # Mock services, synthetic datasets, incident generators
├── scripts/               # Setup, seed, migration, deployment helpers
├── docs/                  # Architecture, ADRs, API notes, runbooks, demo material
├── configs/               # Environment-specific config, topology, patterns, templates
└── .github/workflows/     # CI and deployment scaffolds
```

## Core Backend Areas

- `apps/api-server/src/api`
  REST routes for incidents, approvals, workflow control, health, and evaluations
- `apps/api-server/src/agents`
  Router, Metrics, Logs, Deployment, Root Cause, Risk, Remediation, and Postmortem agent implementations
- `apps/api-server/src/orchestration`
  Workflow graph, node wrappers, checkpoints, state helpers, and interrupt plumbing
- `apps/api-server/src/tools`
  Tool clients and wrappers for Prometheus, Loki, GitHub, Slack, and shared registry primitives
- `apps/api-server/src/db`
  SQLAlchemy models, repositories, and schema bootstrap
- `apps/api-server/src/evaluation`
  Synthetic benchmark runner and scoring modules
- `apps/api-server/src/observability`
  Logging, tracing, and Prometheus metrics helpers

## Frontend

The web dashboard is a Next.js app intended to act as an incident command center. It currently includes pages and components for:

- active incidents
- pending approvals
- evaluation summaries
- workflow/trace surfaces

The UI is structured under:

- `apps/web-dashboard/src/app`
- `apps/web-dashboard/src/features`
- `apps/web-dashboard/src/services`
- `apps/web-dashboard/src/types`

## Implemented Today

The repository currently includes working scaffolding for all planned phases:

- Phase 1-2: project foundation, Docker Compose stack, FastAPI app, health checks, incident intake, database models, repositories
- Phase 3-4: OpenAI-compatible LLM client, tool registry, reusable agent loop, Router Agent, incident-history retrieval scaffolding
- Phase 5-6: Prometheus and Loki wrappers, Metrics and Logs agents, deployment analysis, topology config, GitHub integration scaffolds
- Phase 7-8: evidence normalization, root-cause analysis flow, pattern lookup, confidence scoring, risk assessment, blast-radius scoring
- Phase 9-10: remediation planning, approval flow, workflow checkpointing, resumable orchestration scaffold
- Phase 11-12: postmortem generation, prevention items, evaluation datasets, evaluation summary API, CI evaluation scaffold
- Phase 13-15: dashboard scaffold, hardening scaffolds, deployment assets, docs, ADRs, demo material

## Important Reality Check

This repository is best understood as a substantial prototype and architecture demonstration, not a production-ready AI Ops system yet.

Areas that are present but still scaffolding-heavy include:

- orchestration durability and native LangGraph usage
- approval state persistence
- execution safety enforcement
- end-to-end evaluation realism
- frontend real-time trace visualization
- authentication and RBAC hardening
- production observability depth

If you want a brutally honest gap review against the PRD, see the architecture audit in this conversation or inspect the implementation details in the files below.

## Key Entry Points

- API app: [apps/api-server/src/main.py](/Users/purvansh/Desktop/Projects/SentinalOps/apps/api-server/src/main.py:1)
- Incident routes: [apps/api-server/src/api/routes/incidents.py](/Users/purvansh/Desktop/Projects/SentinalOps/apps/api-server/src/api/routes/incidents.py:1)
- Workflow graph: [apps/api-server/src/orchestration/graphs/main_graph.py](/Users/purvansh/Desktop/Projects/SentinalOps/apps/api-server/src/orchestration/graphs/main_graph.py:1)
- Root-cause agent: [apps/api-server/src/agents/rootcause_agent/agent.py](/Users/purvansh/Desktop/Projects/SentinalOps/apps/api-server/src/agents/rootcause_agent/agent.py:1)
- Risk agent: [apps/api-server/src/agents/risk_agent/agent.py](/Users/purvansh/Desktop/Projects/SentinalOps/apps/api-server/src/agents/risk_agent/agent.py:1)
- Postmortem agent: [apps/api-server/src/agents/postmortem_agent/agent.py](/Users/purvansh/Desktop/Projects/SentinalOps/apps/api-server/src/agents/postmortem_agent/agent.py:1)
- Web dashboard home: [apps/web-dashboard/src/app/page.tsx](/Users/purvansh/Desktop/Projects/SentinalOps/apps/web-dashboard/src/app/page.tsx:1)

## Local Development

### Prerequisites

- Docker and Docker Compose
- Python 3.11+
- Node.js 20+

### Environment

Copy:

```bash
cp .env.example .env
```

### Start the stack

```bash
make up
```

Expected local services:

- API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- Metrics endpoint: `http://localhost:8000/metrics`
- Grafana: `http://localhost:3000`
- Prometheus: `http://localhost:9090`
- Loki: `http://localhost:3100`
- Dashboard: `http://localhost:3001`

## Typical Demo Flow

1. Start the Docker stack.
2. Send a synthetic incident to `POST /incidents/webhook`.
3. Inspect incident state through `GET /incidents` and `GET /incidents/{id}`.
4. Start or resume orchestration through the graph routes.
5. Review approval decisions through `GET /approvals`.
6. Open the dashboard and inspect the command center views.
7. Run the evaluation summary endpoint to inspect benchmark output.

## API Surface

Primary routes currently exposed:

- `POST /incidents/webhook`
- `GET /incidents`
- `GET /incidents/{id}`
- `POST /incidents/{id}/classify`
- `GET /incidents/{id}/postmortems`
- `GET /approvals`
- `POST /approvals/{incident_id}`
- `POST /graph/incidents/{incident_id}/start`
- `POST /graph/incidents/{incident_id}/resume`
- `GET /evaluations/summary`
- `GET /health`
- `GET /metrics`

## Evaluation Assets

Synthetic evaluation fixtures live in:

- `simulation/datasets/evaluation`
- `apps/api-server/src/evaluation`

Current CI scaffolding:

- [evaluation.yml](/Users/purvansh/Desktop/Projects/SentinalOps/.github/workflows/evaluation.yml:1)
- [deploy.yml](/Users/purvansh/Desktop/Projects/SentinalOps/.github/workflows/deploy.yml:1)

## Infrastructure And Deployment

Local infrastructure is defined in:

- [docker-compose.yml](/Users/purvansh/Desktop/Projects/SentinalOps/docker-compose.yml:1)
- `infrastructure/docker/*`

Deployment assets include:

- [infrastructure/render.yaml](/Users/purvansh/Desktop/Projects/SentinalOps/infrastructure/render.yaml:1)
- [apps/api-server/Dockerfile](/Users/purvansh/Desktop/Projects/SentinalOps/apps/api-server/Dockerfile:1)
- [apps/web-dashboard/Dockerfile](/Users/purvansh/Desktop/Projects/SentinalOps/apps/web-dashboard/Dockerfile:1)

## Documentation

- Architecture overview: [docs/architecture/overview.md](/Users/purvansh/Desktop/Projects/SentinalOps/docs/architecture/overview.md:1)
- ADRs: [docs/adr/0001-workflow-graph.md](/Users/purvansh/Desktop/Projects/SentinalOps/docs/adr/0001-workflow-graph.md:1), [docs/adr/0002-evidence-grounding.md](/Users/purvansh/Desktop/Projects/SentinalOps/docs/adr/0002-evidence-grounding.md:1)
- API notes: [docs/api-specs/overview.md](/Users/purvansh/Desktop/Projects/SentinalOps/docs/api-specs/overview.md:1)
- Runbook: [docs/runbooks/oncall-guide.md](/Users/purvansh/Desktop/Projects/SentinalOps/docs/runbooks/oncall-guide.md:1)
- Demo script: [docs/demo-script.md](/Users/purvansh/Desktop/Projects/SentinalOps/docs/demo-script.md:1)

## Recommended Next Steps

- replace the custom workflow engine with real LangGraph `StateGraph`
- move active workflow and approval state into Redis/Postgres-backed durable stores
- harden auth with real JWT/Auth0 validation and route-level enforcement
- turn remediation execution into allowlisted, tool-level gated operations with verification
- make the evaluation runner execute real agents and real workflow paths against mocked tools
- replace dashboard fallbacks with real incident/trace/approval data and interactive controls

## License

This repository includes an MIT-style license in [LICENSE](/Users/purvansh/Desktop/Projects/SentinalOps/LICENSE:1).
