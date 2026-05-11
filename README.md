# SentinelOps AI

**Autonomous Multi-Agent Incident Response and Reliability Orchestration Platform**

SentinelOps AI is a stateful, tool-augmented reasoning engine for production incident investigation. It transforms raw monitoring signals into structured, evidence-grounded insights through a coordinated multi-agent system that mirrors how experienced SREs investigate incidents: gathering heterogeneous telemetry, cross-referencing hypotheses against physical constraints, quantifying risk, and acting only with explicit human oversight for safety-critical decisions.

The platform serves a dual purpose: a realistic enterprise AIOps prototype and a complete reference implementation covering agent decomposition, durable orchestration, pragmatic retrieval, evaluation harnesses, and responsible deployment.

---

## Table of Contents

- [Problem Statement](#problem-statement)
- [System Architecture](#system-architecture)
- [Incident Lifecycle](#incident-lifecycle)
- [Agent System](#agent-system)
- [Technology Stack](#technology-stack)
- [Repository Layout](#repository-layout)
- [Local Development](#local-development)
- [API Reference](#api-reference)
- [Evaluation Framework](#evaluation-framework)
- [Infrastructure and Deployment](#infrastructure-and-deployment)
- [Security Model](#security-model)
- [Current Status](#current-status)
- [Documentation](#documentation)
- [License](#license)

---

## Problem Statement

Production environments continuously generate logs, metrics, traces, and deployment events. When failures occur, engineers must manually correlate disparate signals, reconstruct causal chains, estimate blast radius, and author postmortems after the fact. The result is high Mean Time to Resolution, operator fatigue, inconsistent investigations, and incomplete institutional memory.

Existing observability tools surface alerts. They do not perform structured, evidence-grounded reasoning.

SentinelOps AI fills this gap by:

1. Investigating autonomously — gathering and cross-referencing telemetry without human prompting
2. Reasoning about causality — building explicit evidence chains, not opaque LLM summaries
3. Quantifying risk — computing blast radius and remediation risk with data-driven models
4. Gating execution — pausing for human approval before any high-risk action proceeds
5. Generating postmortems — producing traceable, actionable incident reports that improve over time

---

## System Architecture

```
+--------------------------------------------------+
|              Next.js Dashboard (port 3001)        |
|  Incident board | Agent trace | Approval center   |
+------------------------+--------------------------+
                         |
+------------------------v--------------------------+
|         FastAPI API Gateway (port 8000)           |
|       JWT auth  |  RBAC  |  WebSocket support     |
+------------------------+--------------------------+
                         |
+------------------------v--------------------------+
|       LangGraph Orchestrator (StateGraph)         |
|                                                   |
|  Agent nodes -> Tool nodes -> Human interrupt     |
|  Durable checkpointing via PostgreSQL + Redis     |
|  Conditional edges | Parallel fan-out | Retries   |
+------+------------------+------------------+------+
       |                  |                  |
+------v------+  +--------v-------+  +-------v------+
| Agent Pool  |  | Shared State   |  | Evaluation   |
| (8 agents)  |  | Redis + PG     |  | Module       |
+------+------+  +----------------+  +--------------+
       |
+------v------------------------------------------------------+
|                   Tool Integration Layer                     |
|  Prometheus | Loki | Grafana | GitHub | Slack | PagerDuty   |
|  Qdrant (RAG: runbooks, past incidents, failure patterns)    |
+-------------------------------------------------------------+
```

### Key Architectural Decisions

**Evidence-first data flow.** Agents that query telemetry directly (Metrics, Logs, Deployment) produce structured summaries. Downstream reasoning agents (Root Cause, Risk) are prohibited from making live queries; they work exclusively from those summaries. This prevents iterative correlation-chasing and forces rigorous citation.

**RAG only for static knowledge.** Live telemetry is never injected via vector search. It is always a real-time API call. RAG applies only to past incident summaries, operational runbooks, and the curated failure-pattern library.

**Human interrupt as a first-class node.** The approval step is a native LangGraph `interrupt_before` node, not an ad-hoc API flag. The graph pauses, notifies on-call, and resumes only when an explicit decision arrives.

**Deterministic confidence scoring.** Root cause confidence is not an opaque LLM output. It is a weighted average of evidence coverage, temporal consistency, pattern match score, historical prior probability, and counterfactual power — all transparent and tunable.

---

## Incident Lifecycle

```
Alert fires (Prometheus webhook)
        |
        v
+---------------+
|  Ingest       |  POST /incidents/webhook -> incident row created, Celery task queued
+-------+-------+
        |
        v
+---------------+
|  Classify     |  Router Agent: tags incident type, severity, confidence, recommended workflow
+-------+-------+
        |
        v
+-------+-------+   +---------------+   +------------------+
|  Metrics Agent|   |  Logs Agent   |   | Deployment Agent |  (parallel fan-out)
+-------+-------+   +-------+-------+   +--------+---------+
        |                   |                    |
        +-------------------+--------------------+
                            |
                            v
                  +---------+---------+
                  |  Root Cause Agent |  Builds causal graph, ranks hypotheses with citations
                  +---------+---------+
                            |
                            v
                  +---------+---------+
                  |   Risk Agent      |  Blast radius (Monte Carlo), remediation risk scoring
                  +---------+---------+
                            |
                            v
                  +---------+---------+
                  | Remediation Agent |  Drafts action plan; tags high-risk actions
                  +---------+---------+
                            |
                  [requires_approval?]
                     yes  |   no
                      +---+---+
                      v       v
              +-------+--+   Execute
              |  Approval |
              |  Gate     |  Human reviews risk score + evidence; approve/reject via UI or Slack
              +-------+---+
                      |
                      v
              +-------+-------+
              |   Execute +   |  Run approved actions; verify metrics post-execution
              |   Verify      |
              +-------+-------+
                      |
                      v
              +-------+-------+
              | Postmortem    |  Timeline, 5-Whys narrative, contributing factors, action items
              | Agent         |
              +---------------+
```

---

## Agent System

| Agent | Responsibility | Tools | Safety Constraint |
|---|---|---|---|
| Router | Classify incident type, severity, and recommended workflow | None (pure LLM structured output) | Routes to human triage if confidence < 0.6 |
| Metrics | Fetch Prometheus metrics; surface anomalies with z-scores | `query_prometheus`, `get_service_dependencies` | Read-only; restricted to pre-approved PromQL templates |
| Logs | Search Loki for error signatures, stack traces, temporal patterns | `query_loki`, `expand_log_context`, `extract_stacktrace` | Time-bounded, scoped to affected service |
| Deployment | List recent changes; compute per-deployment risk scores | `get_recent_deployments`, `get_commit_diff`, `get_rollback_candidates` | Read-only |
| Root Cause | Synthesize all evidence into ranked, citation-backed hypotheses | None (reads agent summaries only) | Cannot make live queries; every claim must cite a traceable EvidenceItem |
| Risk | Quantify blast radius and remediation risk with Monte Carlo distribution | Graph traversal + Prometheus traffic data | Deterministic rules engine; LLM only formats results |
| Remediation | Propose action plan ordered by least risk and highest success probability | `execute_action`, `verify_metric` | All high-risk actions tagged `requires_approval`; allowlist enforced at orchestrator layer |
| Postmortem | Generate structured incident report from full trace | Past incidents RAG, ticketing integration | LLM output diffed against source evidence; novel statements flagged |

### Root Cause Confidence Formula

The Root Cause Agent computes a transparent, decomposed confidence score:

```
C = 0.30 * evidence_coverage
  + 0.20 * temporal_consistency
  + 0.20 * pattern_match_score
  + 0.15 * historical_prior
  + 0.15 * counterfactual_power
```

All weights are configurable and tuned through the evaluation harness. If no hypothesis clears a minimum threshold of 0.40, the agent explicitly outputs `insufficient_evidence` with suggested investigation directions rather than fabricating a confident answer.

### Anti-Hallucination Mechanisms

- **Required citations** — every causal claim must reference a traceable `EvidenceItem` by ID
- **Temporal enforcer** — a rule-based pre-processor rejects any hypothesis where an effect precedes its alleged cause
- **Dependency graph validation** — hypotheses proposing causal paths that do not exist in the service topology are automatically eliminated
- **Pattern library grounding** — ~50 curated failure patterns (e.g., thread pool exhaustion, OOMKill restart loop) are retrieved as labeled hints, not as decided answers
- **Explicit unknown output** — below-threshold confidence surfaces as a structured `insufficient_evidence` object

---

## Technology Stack

| Component | Technology | Version |
|---|---|---|
| API server | FastAPI (async) | 0.115.0 |
| Orchestration | LangGraph StateGraph | 0.2.34 |
| LLM inference | OpenAI-compatible (NIM GPT-OSS-120B target) | — |
| Task queue | Celery + Redis | 5.4.0 |
| Primary database | PostgreSQL | 15 |
| Vector store | Qdrant | latest |
| Observability | Prometheus + Loki + Tempo + Grafana | — |
| Caching | Redis | 7 |
| Frontend | Next.js 14 + Tailwind + React Flow | — |
| Containerization | Docker Compose (dev) | — |
| Deployment target | Render / AWS ECS | — |
| Python runtime | 3.11+ | — |
| Node runtime | 20+ | — |

---

## Repository Layout

```
sentinelops-ai/
|
+-- apps/
|   +-- api-server/
|   |   +-- src/
|   |   |   +-- agents/           # Router, Metrics, Logs, Deployment, RootCause, Risk, Remediation, Postmortem
|   |   |   +-- api/              # REST routes: incidents, approvals, graph, evaluations, health
|   |   |   +-- core/             # LLM client, settings, base types
|   |   |   +-- db/               # SQLAlchemy models, repositories, session bootstrap
|   |   |   +-- evaluation/       # Benchmark runner, scoring modules
|   |   |   +-- memory/           # Long-term state helpers
|   |   |   +-- observability/    # Structlog, OpenTelemetry, Prometheus metrics
|   |   |   +-- orchestration/    # LangGraph graph definition, nodes, checkpoints
|   |   |   +-- retrieval/        # Qdrant client, embedding helpers
|   |   |   +-- tools/            # Prometheus, Loki, GitHub, Slack tool clients
|   |   |   +-- workers/          # Celery app, task definitions
|   |   |   +-- main.py           # FastAPI application entry point
|   |   +-- tests/
|   |   +-- Dockerfile
|   |   +-- requirements.txt
|   |
|   +-- web-dashboard/
|       +-- src/
|           +-- app/              # Next.js pages: incidents, approvals, evaluations, trace
|           +-- features/         # Domain feature modules
|           +-- services/         # API client wrappers
|           +-- types/            # Shared TypeScript types
|
+-- infrastructure/
|   +-- docker/                   # Per-service config: Prometheus, Loki, Tempo, Grafana, Postgres
|   +-- render.yaml               # Render deployment manifest
|
+-- simulation/
|   +-- datasets/                 # Synthetic evaluation fixtures (75 scenarios)
|   +-- incident-generators/      # Per-scenario payload generators
|   +-- mock-services/            # Fake Prometheus/Loki responders
|
+-- scripts/
|   +-- demo/                     # Guided demo runner
|   +-- seed/                     # Database seed helpers
|
+-- docs/
|   +-- architecture/             # Current vs. target architecture views
|   +-- adr/                      # Architecture decision records
|   +-- api-specs/                # API documentation
|   +-- runbooks/                 # On-call guides
|   +-- postmortems/              # Sample postmortem outputs
|
+-- configs/                      # Environment-specific topology and pattern configs
+-- .github/workflows/            # CI: evaluation.yml, deploy.yml
+-- docker-compose.yml
+-- docker-compose.simulation.yml
+-- pyproject.toml
+-- Makefile
```

---

## Local Development

### Prerequisites

- Docker and Docker Compose
- Python 3.11 or later
- Node.js 20 or later

### Environment Setup

```bash
cp .env.example .env
# Edit .env and supply a valid LLM_API_KEY
```

### Starting the Full Stack

```bash
make up
```

This builds and starts all services: API server, Celery worker, Celery beat, web dashboard, PostgreSQL, Redis, Qdrant, Prometheus, Loki, Tempo, and Grafana.

### Development Mode (Core Services Only)

```bash
make dev
```

### Running Tests

```bash
make test
```

### Guided Demo

```bash
sh scripts/demo/run_demo.sh
```

### Other Useful Targets

| Command | Description |
|---|---|
| `make down` | Stop and remove all containers |
| `make logs` | Tail all service logs |
| `make migrate` | Run database migrations only |
| `make replay-pending` | Replay any stuck pending incidents |
| `make simulate-up` | Start the simulation stack |
| `make api-shell` | Open a shell inside the API container |

### Service Endpoints

| Service | URL |
|---|---|
| API server | http://localhost:8000 |
| Interactive API docs | http://localhost:8000/docs |
| Prometheus metrics | http://localhost:8000/metrics |
| Grafana | http://localhost:3000 |
| Prometheus | http://localhost:9090 |
| Loki | http://localhost:3100 |
| Tempo | http://localhost:3200 |
| Web dashboard | http://localhost:3001 |
| Qdrant | http://localhost:6333 |

---

## API Reference

### Incidents

| Method | Path | Description |
|---|---|---|
| POST | `/incidents/webhook` | Ingest a Prometheus-style alert payload |
| GET | `/incidents` | List all incidents |
| GET | `/incidents/{id}` | Retrieve a single incident with full state |
| POST | `/incidents/{id}/classify` | Manually trigger classification |
| GET | `/incidents/{id}/postmortems` | Retrieve generated postmortems |

### Approvals

| Method | Path | Description |
|---|---|---|
| GET | `/approvals` | List pending approval requests |
| POST | `/approvals/{incident_id}` | Submit an approval or rejection decision |

### Orchestration Graph

| Method | Path | Description |
|---|---|---|
| POST | `/graph/incidents/{incident_id}/start` | Start a new workflow graph run |
| POST | `/graph/incidents/{incident_id}/resume` | Resume a paused workflow after approval |
| GET | `/graph/incidents/{incident_id}/trace` | Retrieve the full agent execution trace |

### Platform

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/metrics` | Prometheus metrics scrape endpoint |
| GET | `/evaluations/summary` | Retrieve evaluation benchmark summary |

All write endpoints require a bearer token. Obtain one by configuring `JWT_SECRET` and issuing a token with the appropriate roles (`viewer`, `operator`, `admin`). See `.env.example` for configuration.

---

## Evaluation Framework

The evaluation harness enables continuous measurement and guards against regression across prompt and graph changes.

### Synthetic Dataset

75 incidents across the following categories:

- Single-service failures: OOM, CPU saturation, latency spike
- Deployment-induced regressions
- Cascading failures across service dependency chains
- Network partitions
- Insufficient-evidence scenarios (validates `unknown` output path)
- False-positive alerts (metric spikes without real user impact)

Each scenario carries a golden label: incident type, root cause, expected blast radius, correct remediation, and safety classification.

### Evaluation Targets

| Metric | Target | Description |
|---|---|---|
| Classification accuracy | > 90% | Exact or fuzzy match of incident type to golden label |
| Root cause match (top-1) | > 75% | Hypothesis matches golden root cause string or equivalent |
| Evidence grounding score | > 0.95 | Fraction of causal claims traceable to an ingested EvidenceItem |
| Temporal violation rate | 0% | No hypothesis where an effect precedes its alleged cause |
| Hallucination rate | < 5% | Statements not supported by any ingested evidence or pattern |
| Blast radius MAE | < 30% | Mean absolute error of estimated users impacted vs. ground truth |
| Remediation safety | 100% | No high-risk action executes without approval in any run |
| Workflow completion rate | > 98% | Graph reaches a terminal state without crash or dead-end |
| Approval timeout escalation | < 15 minutes | On-call escalation triggers within SLA |

### Running Evaluations

Evaluations are triggered automatically on every pull request that modifies agent prompts or the graph definition via `.github/workflows/evaluation.yml`. Tool responses are mocked for reproducibility.

To run manually:

```bash
GET /evaluations/summary
```

Evaluation assets:

- `simulation/datasets/evaluation/` — synthetic incident fixtures
- `apps/api-server/src/evaluation/` — benchmark runner and scoring modules

---

## Infrastructure and Deployment

### Docker Compose Services

| Service | Image | Purpose |
|---|---|---|
| api-server | Custom (Dockerfile) | FastAPI application + orchestration |
| celery-worker | Custom (Dockerfile) | Asynchronous incident pipeline execution |
| celery-beat | Custom (Dockerfile) | Scheduled task execution |
| web-dashboard | Custom (Dockerfile) | Next.js operator interface |
| postgres | postgres:15 | Checkpoints, incidents, evaluations, audit logs |
| redis | redis:7 | Celery broker, state caching, session data |
| qdrant | qdrant/qdrant:latest | Vector store for runbooks, incidents, patterns |
| prometheus | prom/prometheus:latest | Metrics collection and alerting |
| grafana | grafana/grafana:latest | Dashboards and trace visualization |
| loki | grafana/loki:2.9.8 | Log aggregation |
| tempo | grafana/tempo:2.6.1 | Distributed tracing |

### Deployment

Cloud deployment is configured for Render via `infrastructure/render.yaml`. Dockerfiles are present for both the API server and web dashboard.

```
infrastructure/
+-- docker/
|   +-- postgres/init.sql
|   +-- prometheus/prometheus.yml
|   +-- grafana/datasources.yml
|   +-- loki/loki-config.yaml
|   +-- tempo/tempo.yaml
+-- render.yaml
```

### Failure Handling

| Scenario | Mitigation |
|---|---|
| LLM timeout | Retry with exponential backoff (3 attempts); escalate to human if exhausted |
| Tool API unavailable | Mark as unhealthy, skip, continue with partial evidence, flag in output |
| Human approver unreachable | Escalate after 15 minutes; auto-reject with alert after 30 minutes |
| State corruption | Resume from last PostgreSQL checkpoint; replay deterministic steps |
| Infinite agent loop | Recursion counter; after 2 consecutive re-entries of the same agent, route to human escalation |
| LLM invalid JSON output | Pydantic validation; retry with stricter prompt; fall back to template-based output |

---

## Security Model

- **Authentication** — JWT bearer tokens; Auth0-compatible configuration
- **Authorization** — RBAC roles: `viewer`, `operator`, `admin`. Only operators can approve high-risk actions
- **Tool-level permissions** — each tool carries a `safety_level`; the orchestrator enforces it before execution, independent of the LLM decision
- **Action allowlisting** — destructive tools (e.g., `restart_db`) can be fully disabled via environment configuration; agents never see them in the tool registry
- **Audit logging** — every approval, rejection, tool call, and state change is written to an immutable audit table
- **Prompt injection defense** — system prompts include explicit rejection instructions; input sanitization strips malformed code blocks

---

## Current Status

This repository is a substantial prototype and architecture demonstration. The infrastructure stack boots, the FastAPI server and Celery workers are operational, and Qdrant integration is verified live.

### Verified Working

- Full Docker Compose stack boot
- API server health, metrics, and protected endpoints
- JWT authentication with role enforcement
- Celery worker task registration and Redis queue consumption
- Qdrant collection operations during incident handling
- LangGraph graph compilation and invocation

### Outstanding Blockers

The current release is blocked on a single critical dependency: the router classification step fails when the live LLM provider returns `429 Too Many Requests`, halting the entire incident lifecycle before any agent execution is persisted.

| Blocker | Severity | Required Fix |
|---|---|---|
| End-to-end lifecycle does not complete | Critical | LLM provider fallback or deterministic classifier path |
| No agent executions persisted for live incidents | High | Persist bootstrap checkpoint before first LLM call |
| Approval and remediation paths unproven live | High | Complete one incident through approval and execution |
| Celery async boundary showed loop-closure instability | Medium | Replace `asyncio.run()` task boundary with safer execution model |

### Roadmap

1. Add a deterministic fallback classifier that operates without an external provider
2. Persist the graph bootstrap envelope before the first LLM call
3. Validate the approval and safe-action execution path against a simulated tool
4. Add release-gate smoke tests that assert non-empty graph state after a synthetic incident
5. Replace the custom workflow engine fully with native LangGraph `StateGraph`
6. Move approval state into a Redis/Postgres-backed durable store
7. Harden authentication for production Auth0 JWKS validation
8. Turn remediation execution into allowlisted, tool-level gated operations with post-execution verification

---

## Documentation

| Document | Description |
|---|---|
| [docs/architecture/overview.md](docs/architecture/overview.md) | Architecture index linking current and target views |
| [docs/adr/0001-workflow-graph.md](docs/adr/0001-workflow-graph.md) | ADR: checkpoint-backed workflow graph as orchestration backbone |
| [docs/adr/0002-evidence-grounding.md](docs/adr/0002-evidence-grounding.md) | ADR: evidence grounding and citation enforcement |
| [docs/api-specs/overview.md](docs/api-specs/overview.md) | API design notes |
| [docs/runbooks/oncall-guide.md](docs/runbooks/oncall-guide.md) | On-call operator runbook |
| [docs/demo-script.md](docs/demo-script.md) | Step-by-step guided demo walkthrough |
| [PRD.md](PRD.md) | Full product requirements document |
| [FINAL_ENGINEERING_REPORT.md](FINAL_ENGINEERING_REPORT.md) | Release validation report |
| [PRODUCTION_BLOCKERS.md](PRODUCTION_BLOCKERS.md) | Current release blockers |
| [ARCHITECTURE_RISK_REGISTER.md](ARCHITECTURE_RISK_REGISTER.md) | Identified architectural risks and mitigations |

---

## License

Released under the MIT License. See [LICENSE](LICENSE) for details.
