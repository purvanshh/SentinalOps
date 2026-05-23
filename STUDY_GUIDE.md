# SentinelOps AI: Technical Study Guide

## 1. Executive Overview

### What It Is

SentinelOps AI is an uncertainty-aware incident reasoning system for infrastructure operations. It ingests alert payloads from monitoring systems (Prometheus, PagerDuty, custom webhooks), classifies them, gathers evidence from metrics/logs/deployment history, performs probabilistic root-cause analysis, proposes risk-ranked remediations, and gates execution behind operator approval.

### Core Problem

Production incident response is slow, error-prone, and cognitively expensive. On-call engineers must correlate signals across metrics, logs, deployments, and topology under time pressure. SentinelOps attempts to automate the investigation phase while keeping humans in the loop for execution decisions.

### Target Users

- SRE teams managing distributed services
- On-call engineers needing faster incident triage
- Platform teams wanting structured postmortem generation
- Organizations exploring AI-assisted operations without full autonomy

### Key Capabilities

1. Structured incident classification via LLM with vector-search augmentation
2. Parallel evidence gathering (metrics, logs, deployment history)
3. Algorithmic root-cause analysis with uncertainty quantification
4. Topology-aware blast-radius estimation via Monte Carlo simulation
5. Risk-tiered remediation planning with operator approval gates
6. Deterministic evaluation framework with 121-incident benchmark suite
7. Multi-layer provider resilience (4-layer failover chain)
8. Causal hallucination detection (topology, temporal, deployment constraints)

### Engineering Maturity

This is a research-grade system with production-quality infrastructure patterns. The orchestration, persistence, evaluation, and safety layers are well-engineered. The actual reasoning quality (root-cause accuracy 0.0820) is experimental. The system is honest about this gap.

### Technical Sophistication

High. The codebase demonstrates: LangGraph state machines with interrupt/resume, probabilistic reasoning with calibration scoring, causal event graphs, circuit breakers with operating mode management, evaluation integrity enforcement (golden label isolation), and structured observability with Prometheus counters/histograms.

---

## 2. High-Level System Architecture

### Architecture Style

Monolithic backend with internal modular boundaries, deployed as multiple processes (API server, Celery workers, Celery beat scheduler) sharing a single codebase. The frontend is a separate Next.js application communicating via REST API.

### Runtime Boundaries

```
[Alert Sources] --> [FastAPI API Server] --> [PostgreSQL]
                         |                       ^
                         v                       |
                    [Redis Queue]                 |
                         |                       |
                         v                       |
                  [Celery Workers] -------->-----+
                         |
                         v
                  [LangGraph Engine]
                         |
                    +---------+----------+
                    |         |          |
                    v         v          v
              [LLM Provider] [Qdrant] [Observability Stack]
```

### Why This Architecture

1. **Monolith over microservices**: Single team, shared domain model, no need for service boundaries. The modular internal structure (agents/, orchestration/, evaluation/) provides separation without network overhead.

2. **Celery over in-process async**: Incident pipelines are long-running (30s-5min). Celery provides crash recovery, retry with backoff, dead-letter queues, and worker isolation. A crashed worker does not take down the API server.

3. **LangGraph over custom state machine**: LangGraph provides interrupt/resume semantics, parallel fan-out via `Send`, checkpointing, and conditional routing. Building this from scratch would be months of work.

4. **PostgreSQL as source of truth**: Incidents, agent executions, evidence, approvals, and checkpoints all need ACID guarantees. The relational model maps naturally to the domain (incident has many executions, each execution has one agent).

5. **Redis for ephemeral state**: Short-term incident state (1-hour TTL) for fast graph state access without hitting PostgreSQL on every node transition.

6. **Qdrant for vector search**: Semantic similarity over runbooks, patterns, incident history, and operational memory. Separate from PostgreSQL because vector operations have different scaling characteristics.

### Communication Flow

1. Webhook arrives at FastAPI
2. Incident persisted to PostgreSQL
3. Celery task enqueued to Redis
4. Worker picks up task, invokes LangGraph
5. Graph nodes call LLM providers, Qdrant, and write back to PostgreSQL
6. State checkpointed at each node boundary
7. If approval needed: graph interrupts, waits for resume command
8. Results persisted, postmortem generated

### State Management

Three-tier state:
- **PostgreSQL**: Durable, survives restarts. Incidents, executions, checkpoints.
- **Redis**: Ephemeral, fast. Current graph state, LLM response cache.
- **In-process**: LangGraph MemorySaver for interrupt/resume within a single worker process.

---

## 3. Repository Structure Deep Dive

### `apps/api-server/src/` - The Core Backend

This is the entire backend application. Everything runs from this directory via `PYTHONPATH=apps/api-server/src`.

**`agents/`** - Domain-specific reasoning modules. Each agent is a self-contained unit with its own prompts, output schema, and execution logic. The router agent classifies; metrics/logs/deployment agents gather evidence; rootcause performs probabilistic analysis; risk estimates blast radius; remediation plans actions; postmortem generates reports. The `base_agent.py` provides the generic tool-calling `agent_loop` that most agents use.

**`api/`** - FastAPI HTTP layer. Routes, middleware (auth, error handling), schemas (Pydantic request/response models), dependencies (DB session injection, role checking), and WebSocket streaming. This is a thin layer that delegates to agents and orchestration.

**`causality/`** - Causal reasoning engine (Phase 43). Contains the `CausalEventGraph` (directed graph of operational events), `TemporalEngine` (temporal ordering and contradiction detection), `HallucinationDetector` (topology/temporal/deployment constraint validation), and the `reality/` subdirectory with ambiguity resolution, stability analysis, and collapse guards.

**`core/`** - Application infrastructure. Config (pydantic-settings), LLM client (httpx-based OpenAI-compatible), exceptions, and the `resilience/` module (circuit breakers, provider chain, operating modes, deterministic fallback classifier).

**`db/`** - Persistence layer. SQLAlchemy 2.0 async models, repository pattern, session management, migrations. 14 models covering the full domain.

**`evaluation/`** - Benchmark and scoring framework. The `runner.py` executes real agent cognition against mocked infrastructure. The `orchestration_runner.py` is the detailed pipeline executor. `execution_mode.py` enforces the EVALUATION/PRODUCTION boundary. `regression/` contains deterministic replay and chaos integration.

**`memory/`** - Two-tier memory. `short_term/` is Redis-backed incident state with TTL. `long_term/` and `operational_memory.py` provide six-category Qdrant-backed semantic memory (incident, remediation, deployment, topology, noisy alert, escalation patterns).

**`observability/`** - Prometheus metrics (30+ counters/histograms), structured logging (structlog with JSON rendering and context vars), OpenTelemetry tracing (OTLP to Tempo or console fallback). The `reality/` subdirectory contains telemetry integrity checking for the evaluation framework.

**`orchestration/`** - LangGraph workflow. The `main_graph.py` defines the full incident pipeline as a StateGraph. `nodes/` contains individual node implementations. `state/` defines the TypedDict state schema with annotated reducers. `checkpointing/` provides PostgreSQL-backed checkpoint persistence. `interrupts/` handles approval gate mechanics.

**`retrieval/`** - Vector search layer. `hybrid_retrieval.py` combines pattern search with topology-aware re-ranking and temporal decay. `retrieval_orchestrator.py` manages Qdrant collection lifecycle. `provenance.py` attaches grounding metadata to every retrieved item.

**`tools/`** - Agent tool system. `base.py` defines ToolCall/ToolResult types. `registry.py` provides decorator-based tool registration with OpenAI function-calling schema generation. `execution_guard.py` enforces allowlist + JWT approval token validation. `risk_classifier.py` classifies actions into four risk tiers.

**`workers/`** - Celery infrastructure. `queues.py` configures the Celery app with task routing, serialization security, and time limits. `tasks/` contains the incident pipeline task with heartbeat monitoring and dead-letter handling. `schedulers/` runs periodic approval timeout checks.

### `simulation/` - Evaluation Data

**`datasets/evaluation/benchmark_suite_v1.json`** - 121 labeled incidents with golden classifications, root causes, remediation classes, operator actions, and confidence ranges. This is the ground truth for all evaluation.

**`datasets/operational_chaos/incidents.json`** - 40 incidents with 13 chaos profiles (alert_storm, clock_skew, split_brain, etc.) for testing system behavior under degraded conditions.

**`datasets/live_replay/incidents.json`** - 25 incidents with 100 telemetry events for operational replay testing.

**`mock-services/`** - Four FastAPI mock services (payment, auth, notification, gateway) for local simulation.

### `configs/` - Environment-Specific Configuration

**`production/tool_allowlist.yaml`** - Defines which tools are dangerous (rollback_deployment, restart_service, scale_service) and which require approval (verify_metric). This is the safety boundary.

**`development/topology.yaml`** - Service dependency graph (4 services: payment-api, auth-service, cache-service, postgres-db). Used for blast-radius estimation and topology-aware retrieval.

---

## 4. Technology Stack Analysis

### Backend Runtime

| Technology | Version | Why Chosen |
|-----------|---------|------------|
| Python 3.11 | 3.11+ | Async/await maturity, type hints, performance improvements over 3.10 |
| FastAPI | 0.115.0 | Async-native, Pydantic integration, OpenAPI generation, dependency injection |
| SQLAlchemy | 2.0.35 | Async support (2.0 style), mature ORM, PostgreSQL JSONB support |
| Celery | 5.4.0 | Battle-tested task queue, retry/backoff, dead-letter, worker isolation |
| LangGraph | 0.2.34 | State machine orchestration with interrupt/resume, parallel fan-out, checkpointing |
| Pydantic | 2.9.2 | Validation, serialization, settings management, structured output parsing |
| httpx | 0.27.2 | Async HTTP client for LLM providers, connection pooling |
| structlog | 24.4.0 | Structured JSON logging with context variables |
| Redis | 5.0.8 | Celery broker, short-term state cache, LLM response cache |
| prometheus-client | 0.20.0 | Native Prometheus metrics exposition |
| OpenTelemetry | 1.27.0 | Distributed tracing to Tempo |
| python-jose | 3.3.0 | JWT token creation/validation for approval tokens |

**Key tradeoff**: LangGraph 0.2.34 is a relatively early version. The API has changed significantly in later versions. This pins the project to specific LangGraph semantics (StateGraph, Send, interrupt_before) that may not be forward-compatible.

**Hidden implication**: `greenlet==3.1.1` is required by SQLAlchemy's async engine. It's a C extension that can cause build issues on some platforms.

### Frontend

| Technology | Version | Why |
|-----------|---------|-----|
| Next.js | 14.2.15 | React framework with SSR, API routes, file-based routing |
| React | 18.3.1 | UI library |
| TypeScript | 5.6.2 | Type safety |

The frontend is minimal. No state management library, no UI component library, no data fetching library beyond fetch. This suggests the dashboard is secondary to the backend.

### Infrastructure

| Component | Image/Version | Role |
|-----------|--------------|------|
| PostgreSQL | 15 | Primary data store |
| Redis | 7 | Queue broker, cache |
| Qdrant | latest | Vector search |
| Prometheus | latest | Metrics collection |
| Grafana | latest | Dashboards |
| Loki | 2.9.8 | Log aggregation |
| Tempo | 2.6.1 | Distributed tracing |

**Risk**: Using `latest` tags for Qdrant, Prometheus, and Grafana means builds are not reproducible. A breaking change in any of these could silently break the stack.

### Development Tools

| Tool | Purpose |
|------|---------|
| Ruff | Linting (replaces flake8, isort, pyflakes) |
| Black | Code formatting |
| pytest | Testing with asyncio support |
| respx | HTTP mocking for provider chain tests |
| Docker Compose | Local development orchestration |

---

## 5. Dependency Analysis

### Critical Dependencies

**LangGraph 0.2.34** - The entire orchestration layer depends on this. It's the most architecturally significant dependency. Upgrading requires understanding breaking changes in StateGraph API, Send semantics, and checkpointer interfaces.

**SQLAlchemy 2.0.35** - Every database interaction flows through this. The async session pattern (`async_sessionmaker`) is used throughout. The JSONB column type stores agent inputs/outputs.

**Celery 5.4.0** - Task execution, retry logic, dead-letter handling. The configuration in `queues.py` is carefully tuned (acks_late, reject_on_worker_lost, prefetch_multiplier=1, time limits).

### Transitive Risks

- `langgraph` pulls in `langchain-core`, `langsmith`, and potentially many LangChain ecosystem packages
- `psycopg[binary]` includes compiled PostgreSQL client libraries
- `python-jose[cryptography]` pulls in `cryptography` which has complex native dependencies

### Versioning Strategy

All dependencies are pinned to exact versions in both `pyproject.toml` and `requirements.txt`. This is correct for reproducibility but means manual upgrade effort.

### Dangerous Dependencies

- `python-jose` is effectively unmaintained. The recommended replacement is `PyJWT` or `joserfc`. Security patches may not arrive.
- `langgraph==0.2.34` is very early. The LangGraph API has evolved significantly. This version may have unfixed bugs.

---

## 6. Core Domain Model

### Entities

```
Incident (central entity)
  ├── AgentExecution[] (one per agent that processed this incident)
  ├── EvidenceItem[] (normalized evidence from metrics/logs/deployment)
  ├── RemediationAction[] (proposed actions with approval status)
  ├── ApprovalRequest (one pending approval per incident)
  ├── Evaluation[] (scoring results)
  ├── Postmortem[] (generated reports)
  └── WorkflowCheckpoint[] (graph state snapshots)

PendingTask (deferred/failed pipeline executions)
RemediationHistory (historical action outcomes for risk scoring)
AuditLog (security audit trail)
PreventionItem (action items from postmortems)
```

### State Transitions (Incident)

```
open → classified → investigating → awaiting_approval → executing → resolved
  │        │                                                           │
  │        └──→ needs_triage (low confidence)                          │
  │                                                                    │
  └──→ failed (unrecoverable error)                                    │
                                                                       │
approval_rejected ←────────────────────────────────────────────────────┘
```

### Invariants

1. An incident always has a `raw_payload` (the original alert)
2. Agent executions are append-only (never modified after creation)
3. Approval tokens are scoped to specific incident + action IDs
4. Evidence items are replaced atomically (delete all, insert new)
5. Remediation actions require `approved=True` before execution
6. Dangerous tools require a valid JWT approval token

---

## 7. End-to-End Data Flow

### Incident Lifecycle (Complete Trace)

**Step 1: Alert Ingestion**
```
POST /incidents/webhook
  Body: { title, severity, source, summary, raw_payload }
  Auth: Bearer token with "admin" role
  → Pydantic validation (AlertPayload schema)
  → IncidentRepository.create_from_alert()
  → PostgreSQL INSERT into incidents table
  → observe_incident_created() Prometheus counter
  → enqueue_incident_pipeline(incident_id)
  → Return 201 with IncidentResponse
```

**Step 2: Task Enqueue**
```
enqueue_incident_pipeline()
  → PendingTaskRepository.create_pending_task() [PostgreSQL record]
  → run_incident_pipeline.delay(incident_id) [Redis LPUSH]
  → If Redis unavailable: task stays in pending_tasks table for replay
```

**Step 3: Worker Pickup**
```
Celery worker dequeues from "incidents" queue
  → run_incident_pipeline(incident_id)
  → mark_running_by_incident() [update pending_tasks with worker_run_id]
  → reset_graph() [clear stale async clients]
  → build_main_graph() [singleton LangGraphWorkflow]
  → Start heartbeat task (every 5s updates pending_tasks.updated_at)
```

**Step 4: Graph Bootstrap**
```
LangGraphWorkflow.ainvoke()
  → Generate thread_id, execution_id
  → Build initial IncidentState:
    { incident_id, thread_id, execution_id, status: "starting",
      operating_mode: "FULL", started_at, remaining_steps: 12 }
  → PERSIST to Redis BEFORE any LLM call
  → Log "workflow_bootstrap_persisted"
  → Invoke LangGraph StateGraph
```

**Step 5: Router Node**
```
router_node(state)
  → IncidentRepository.get(incident_id) [PostgreSQL]
  → Build alert_payload dict from incident fields
  → IncidentHistorySearcher.search_similar_incidents() [Qdrant]
  → ResilientLLMClient.classify_with_fallback():
      Layer 1: Primary provider POST /chat/completions
        → If 429: CircuitBreaker.record_failure(), backoff, retry
      Layer 2: Secondary provider (if primary exhausted)
      Layer 3: Local Ollama
      Layer 4: DeterministicFallbackClassifier.classify()
  → Parse RouterOutput (incident_type, severity, confidence, rationale)
  → IncidentRepository.update_classification()
  → IncidentRepository.create_agent_execution()
  → Return state update: { classification, status, operating_mode }
```

**Step 6: Conditional Routing**
```
route_after_router(state)
  → If remaining_steps <= 0: → "triage" (END)
  → If status == "needs_triage": → "triage" (END)
  → Else: → "fanout" → dispatch_evidence
```

**Step 7: Parallel Evidence Collection**
```
fan_out_evidence(state) → LangGraph Send():
  → Send("metrics", state)  [parallel]
  → Send("logs", state)     [parallel]
  → Send("deployment", state) [parallel]

Each evidence agent:
  → agent_loop(llm_client, system_prompt, tools, registry)
  → LLM generates tool calls → registry.execute() → tool results
  → LLM produces structured output (MetricsSummary/LogsSummary/DeploymentSummary)
  → IncidentRepository.create_agent_execution()
```

**Step 8: Root Cause Analysis**
```
rootcause_node(state)
  → normalize_agent_executions() [flatten evidence into standard format]
  → replace_evidence_items() [atomic PostgreSQL update]
  → build_timed_events() [construct temporal event sequence]
  → load_topology() [YAML service graph]
  → HybridRetriever.retrieve() [Qdrant pattern search + topology re-ranking]
  → build_candidate_causes() [topology + evidence type matching]
  → build_probabilistic_root_cause_analysis():
      → UncertaintyEngine assessment
      → Hypothesis probability distribution
      → Calibration temperature scaling
      → Escalation decision
  → Emit observability metrics (confidence, calibration, stability)
  → IncidentRepository.update_root_cause()
```

**Step 9: Risk Assessment**
```
risk_node(state)
  → compute_blast_radius(service, topology, traffic, severity_factor)
      → Topology traversal (BFS over dependency graph)
      → Monte Carlo simulation (1000 samples, seed=42)
  → score_remediation_action() for each candidate action
  → Persist RiskAssessment
```

**Step 10: Remediation Planning**
```
remediation_node(state)
  → Read risk_agent execution output
  → Build RemediationPlan with priority-ordered steps
  → Each step: { action, requires_approval, rationale, verification_metric }
  → IncidentRepository.replace_remediation_actions()
```

**Step 11: Approval Gate**
```
approval_node(state)
  → If any step requires_approval AND risk_tier >= HIGH:
      → Create ApprovalRequest in PostgreSQL
      → Set status = "awaiting_approval"
      → Graph INTERRUPTS (LangGraph interrupt_before)
      → Celery beat polls every 5 minutes for timeout
      → If timeout: escalate_approval → Slack notification → auto-reject
  → If no approval needed: continue to execution
```

**Step 12: Execution**
```
execution_node(state)
  → For each approved action:
      → classify_action_risk_tier(action)
      → enforce_tool_execution_policy():
          → Check tool_allowlist.yaml
          → If dangerous: validate JWT approval token
          → If not allowlisted: BLOCK
      → Execute tool via registry
      → AuditLogRepository.create_event()
```

**Step 13: Postmortem**
```
postmortem_node(state)
  → Gather all agent executions for incident
  → Generate structured postmortem (timeline, contributing factors, action items)
  → Persist Postmortem to PostgreSQL
  → Index resolved incident to Qdrant (for future retrieval)
```

---

## 8. Detailed Module Breakdown

### Router Agent (`agents/router_agent/`)

**Purpose**: Classify incoming incidents into categories (latency, cpu, memory, deployment, database, networking, etc.) with confidence scores.

**Inputs**: Alert payload (title, summary, severity, source, labels, annotations) + similar historical incidents from Qdrant.

**Outputs**: `RouterOutput` (incident_type, severity, confidence, requires_immediate_investigation, recommended_workflow, rationale).

**Design Pattern**: Direct LLM call with structured output parsing. No tool-calling loop. The router is intentionally simple and fast.

**Failure Mode**: If confidence < 0.6, routes to human triage instead of automation. This is the safety valve.

### Root Cause Agent (`agents/rootcause_agent/`)

**Purpose**: Determine the most likely cause of an incident from normalized evidence.

**Architecture**: Entirely algorithmic after evidence normalization. No LLM in the hot path.

```
evidence_normalizer.py → Flatten agent outputs into standard evidence items
evidence_builder.py → Construct timed events with temporal ordering
causal_graph.py → Generate candidate causes from topology + evidence
probabilistic_reasoner.py → Score candidates, distribute probability, assess uncertainty
```

**Key Insight**: The root-cause agent does NOT call an LLM. It uses the UncertaintyEngine to distribute probability across competing hypotheses using temperature-scaled softmax. This makes it deterministic and testable.

**Weakness**: Root-cause accuracy is 0.0820 because candidate generation is heuristic (keyword matching against topology), not learned.

### Risk Agent (`agents/risk_agent/`)

**Purpose**: Estimate blast radius and score remediation action risk.

**Algorithm** (`blast_radius.py`):
1. BFS traversal from affected service through topology dependency graph
2. Count downstream services at each hop
3. Monte Carlo simulation (1000 samples, `random.Random(42)`) over traffic snapshots
4. Combine topology reach + traffic volume + severity factor

**Algorithm** (`action_risk.py`):
1. Look up historical success rate for similar actions
2. Weight by execution time and severity-on-failure
3. Produce risk score and recommendation

### Resilience Module (`core/resilience/`)

**Purpose**: Ensure the incident pipeline survives LLM provider failures.

**Components**:
- `fallback_classifier.py`: Zero-dependency keyword/regex classifier (Layer 4)
- `provider_chain.py`: Multi-layer failover with per-provider circuit breakers
- `circuit_breaker.py`: CLOSED/OPEN/HALF_OPEN state machine per provider
- `operating_mode.py`: FULL/DEGRADED/LOCAL_ONLY/SAFE_MODE/OBSERVE_ONLY
- `resilient_llm_client.py`: High-level client integrating chain + fallback

**Design Decision**: The fallback classifier uses scoring (keyword=+1, regex=+2) rather than first-match. This handles incidents that match multiple categories by picking the strongest signal.

### Evaluation Framework (`evaluation/`)

**Purpose**: Measure system quality without contaminating agent reasoning with golden labels.

**Critical Invariant**: `_assert_no_golden_contamination()` checks that golden labels are not present in mocked_tool_responses. This was the Phase 40 fix that invalidated all prior scores.

**Two Modes**:
1. `run_evaluation()` - Real agent cognition with mocked infrastructure
2. `replay_benchmark()` - Deterministic scoring from labels without agent execution

**Scoring Dimensions**: Classification accuracy, root-cause text overlap, grounding (citation validity), hallucination detection, blast-radius match, safety (no CRITICAL actions in safe incidents).

---

## 9. Decision Analysis

### Decision: LangGraph over Custom State Machine

**What was chosen**: LangGraph StateGraph with compiled workflow, interrupt_before, and Send for parallel dispatch.

**Alternatives**: Custom async state machine, Temporal.io, Prefect, Airflow, raw asyncio with manual checkpointing.

**Why LangGraph won**: It provides interrupt/resume semantics (critical for approval gates), parallel fan-out (Send), built-in checkpointing, and conditional routing. The approval gate pattern (interrupt_before a node, resume with a Command) would require significant custom code otherwise.

**Tradeoffs**: LangGraph is young (0.2.x), API-unstable, and tightly coupled to the LangChain ecosystem. Upgrading is risky. The project mitigates this by wrapping LangGraph in `LangGraphWorkflow` class, providing a stable internal interface.

### Decision: Algorithmic Root Cause over LLM-Based RCA

**What was chosen**: The root-cause agent uses algorithmic scoring (evidence normalization → timed events → candidate generation → probabilistic scoring) without calling an LLM.

**Alternatives**: Have the LLM reason about root cause directly from evidence, use a chain-of-thought prompt, or use a fine-tuned model.

**Why algorithmic won**: Determinism, testability, and auditability. An LLM-based RCA would produce different outputs on each run, making evaluation impossible. The algorithmic approach produces identical results for identical inputs, enabling regression testing.

**Tradeoffs**: Root-cause accuracy is 0.0820. The heuristic candidate generation (keyword matching against topology) is too shallow for real-world incidents. A hybrid approach (LLM for candidate generation, algorithm for scoring) would likely perform better.

### Decision: Celery over In-Process Async

**What was chosen**: Celery with Redis broker for incident pipeline execution.

**Alternatives**: In-process asyncio tasks, FastAPI BackgroundTasks, Dramatiq, Huey, or direct LangGraph async invocation from the API handler.

**Why Celery won**: Worker isolation (crashed pipeline doesn't crash API), retry with exponential backoff, dead-letter queues, task routing (separate queues for incidents vs approvals), time limits (soft 5min, hard 6min), and the `acks_late + reject_on_worker_lost` pattern for crash recovery.

**Tradeoffs**: Celery adds operational complexity (separate worker process, beat scheduler, Redis dependency). The `asyncio.run()` bridge in `run_incident_pipeline` is a known anti-pattern (running async code from sync Celery task), but it works because each task gets its own event loop.

### Decision: Repository Pattern over Direct ORM

**What was chosen**: Repository classes (`IncidentRepository`, `PendingTaskRepository`, etc.) wrapping SQLAlchemy queries.

**Alternatives**: Direct session queries in route handlers, Django-style model methods, CQRS.

**Why repositories won**: Testability (repositories can be mocked), separation of concerns (routes don't know about SQL), and the ability to add cross-cutting concerns (observability metrics on every agent execution creation).

### Decision: JWT Approval Tokens over Session-Based Approval

**What was chosen**: Cryptographically signed JWT tokens scoped to specific incident + action IDs, with expiration.

**Alternatives**: Database-stored approval flags, session cookies, API key-based approval.

**Why JWT won**: Stateless verification (no DB lookup needed at execution time), tamper-proof (HMAC-SHA256), scoped (token only valid for specific actions on specific incident), and time-limited. This prevents replay attacks and scope escalation.

### Decision: Deterministic Fallback Classifier over Graceful Failure

**What was chosen**: A zero-dependency keyword/regex classifier that activates when all LLM providers fail.

**Alternatives**: Return an error and halt the pipeline, queue for later retry, use a cached previous classification.

**Why fallback won**: The pipeline must never leave an incident in limbo. A deterministic classification (even with lower confidence) allows the pipeline to continue gathering evidence and generating a postmortem. The operator sees the fallback was used (full transparency in state).

### Decision: Evaluation Integrity Enforcement over Trust

**What was chosen**: Explicit `_assert_no_golden_contamination()` guard that raises ValueError if golden labels leak into agent inputs.

**Alternatives**: Trust developers not to leak labels, code review only, separate golden labels into a different file format.

**Why enforcement won**: The project discovered (Phase 40) that prior evaluation was constructing outputs from golden labels before scoring. This made all metrics meaningless. The runtime assertion prevents regression. It's a hard failure rather than a silent corruption.

### Decision: Operating Modes over Binary On/Off

**What was chosen**: Five explicit operating modes (FULL, DEGRADED, LOCAL_ONLY, SAFE_MODE, OBSERVE_ONLY) with automatic transitions.

**Alternatives**: Binary healthy/unhealthy, three-state (normal/degraded/down), no explicit mode tracking.

**Why five modes won**: Each mode has distinct behavioral implications. DEGRADED still allows LLM calls (just from secondary). LOCAL_ONLY uses Ollama. SAFE_MODE uses deterministic fallback only. OBSERVE_ONLY records but takes no action. This granularity lets operators understand exactly what the system can and cannot do at any moment.

---

## 10. Algorithms and Internal Logic

### Probabilistic Root Cause Scoring

The `probabilistic_reasoner.py` implements:

1. **Candidate generation**: Topology traversal + evidence type matching produces candidate causes
2. **Evidence scoring**: Each candidate scored by how many evidence items support it
3. **Temperature-scaled softmax**: Probabilities distributed across candidates using `calibration_temperature=1.35`
4. **Uncertainty assessment**: UncertaintyEngine evaluates evidence quality, contradictions, and hypothesis stability
5. **Escalation decision**: If confidence < 0.55 or contradictions detected, recommend operator escalation

The temperature of 1.35 (above 1.0) systematically pushes probabilities toward 0.5, causing the 87.5% underconfidence rate observed in benchmarks. This is a deliberate conservative choice: better to underconfident and escalate than overconfident and execute wrong remediation.

### Blast Radius Monte Carlo

```python
def compute_blast_radius(service, topology, traffic, severity_factor):
    # 1. BFS from service through dependency graph
    downstream = bfs_downstream(service, topology)
    
    # 2. Monte Carlo: sample traffic impact
    rng = random.Random(42)  # deterministic
    samples = []
    for _ in range(1000):
        impact = sum(
            traffic[svc]["rps"] * rng.uniform(0.1, severity_factor)
            for svc in downstream
        )
        samples.append(impact)
    
    # 3. Return distribution statistics
    return { mean, p50, p95, p99, users_at_risk }
```

The seed=42 makes this deterministic for testing. In production, you'd want actual traffic data rather than static snapshots.

### Circuit Breaker State Machine

```
CLOSED ──(failure_count >= threshold)──→ OPEN
OPEN ──(recovery_timeout elapsed)──→ HALF_OPEN
HALF_OPEN ──(success)──→ CLOSED
HALF_OPEN ──(failure)──→ OPEN
```

Each provider has its own circuit breaker. The recovery timeout (30s for primary, 20s for secondary, 15s for local) determines how quickly the system retests a failed provider.

### Temporal Contradiction Detection

The `temporal_engine.py` detects impossible causal claims:
- A deployment that occurred AFTER the anomaly started cannot be the root cause
- An event cannot cause something that preceded it in time
- Propagation must respect the configured window (default 300s)

### Hybrid Retrieval Scoring

```
hybrid_score = base_similarity * time_decay + topology_boost

where:
  time_decay = exp(-ln(2) * age_days / 90)  # half-life of 90 days
  topology_boost = 0.10 if result_service is neighbor of query_service
```

This ensures recent incidents from related services rank higher than old incidents from unrelated services.

---

## 11. Configuration System

### Environment Variables (via pydantic-settings)

The `Settings` class loads from `.env` file with fallback defaults. Key groups:

**Database**: `POSTGRES_SERVER`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`

**Queue**: `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `REDIS_URL`

**LLM Providers**: `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` (primary), `LLM_SECONDARY_*` (secondary), `LLM_LOCAL_*` (Ollama), `NVIDIA_*` (NVIDIA NIM)

**Auth**: `AUTH0_DOMAIN`, `AUTH0_AUDIENCE`, `AUTH0_SECRET_KEY`, `APPROVAL_TOKEN_SECRET`

**Observability**: `PROMETHEUS_URL`, `GRAFANA_URL`, `LOKI_URL`, `TEMPO_URL`

### Production Secret Validation

`Settings.validate_production_secrets()` checks that default development secrets are not used in production. The API server hard-fails on startup if insecure defaults are detected in production mode.

### Configuration Risks

1. `@lru_cache` on `get_settings()` means settings are loaded once and never refreshed. Environment variable changes require process restart.
2. The `tool_allowlist_path` is read from disk on every tool execution (no caching). This is safe but adds filesystem I/O to the hot path.
3. Default `LLM_MODEL=gpt-oss-120b` is a placeholder that will fail against real providers.

---

## 12. Database and Persistence Layer

### Schema Design

14 tables with UUID primary keys, JSONB for flexible payloads, and timestamp mixins (created_at, updated_at with server_default=func.now()).

**Key relationships**:
- Incident → AgentExecution (1:many, cascade delete)
- Incident → EvidenceItem (1:many, cascade delete)
- Incident → RemediationAction (1:many, cascade delete)
- Incident → ApprovalRequest (1:1, cascade delete)
- Incident → Postmortem (1:many, cascade delete)

**JSONB usage**: `raw_payload`, `input`, `output`, `details`, `content`, `payload`, `state`, `actions`. This provides schema flexibility for agent outputs that vary by agent type.

### Migration Strategy

`initialize_database()` uses `Base.metadata.create_all()` — a development-only approach that creates tables if they don't exist but cannot handle schema evolution. There is a `db/migrations/` directory but no Alembic configuration visible. This is a gap for production deployment.

### Query Patterns

- `selectinload` for eager loading relationships (avoids N+1)
- Repository methods return domain objects, not raw rows
- Atomic evidence replacement (delete all + insert new in single transaction)
- UUID coercion helper (`_coerce_uuid`) handles both UUID objects and strings

### Scaling Concerns

- No explicit indexes beyond primary keys and the few `index=True` columns (thread_id on checkpoints, incident_id on pending_tasks)
- JSONB columns are not indexed — queries filtering on JSON fields will table-scan
- The `selectinload` pattern loads all related objects eagerly, which could be expensive for incidents with many executions

---

## 13. API Design Review

### Endpoint Structure

```
POST /incidents/webhook          - Create incident from alert
GET  /incidents                  - List incidents (optional status filter)
GET  /incidents/{id}             - Get incident with executions
POST /incidents/{id}/classify    - Re-classify existing incident
GET  /incidents/{id}/postmortems - List postmortems

POST /approvals/{id}/decide      - Approve/reject remediation
GET  /approvals/pending          - List pending approvals

POST /graph/start                - Start graph for incident
POST /graph/resume               - Resume interrupted graph
GET  /graph/{thread_id}/state    - Get current graph state

GET  /evaluations/summary        - Run evaluation and return results

GET  /health                     - Health check with service status
GET  /metrics                    - Prometheus metrics endpoint
WS   /ws/incidents/{id}          - Real-time incident updates
```

### Auth Model

JWT-based with role checking. Roles: admin, operator, viewer. The `require_role` dependency enforces minimum role per endpoint. Auth middleware validates tokens using Auth0 configuration (or HS256 symmetric key in development).

### Error Handling

Three-tier exception handling:
1. `HTTPException` → structured JSON error response
2. `PermissionError` → 403 with role information
3. `Exception` (catch-all) → 500 with generic message (no stack trace in response)

Request IDs are propagated via `x-request-id` header for correlation.

---

## 14. Frontend Architecture

The Next.js dashboard is minimal:
- No state management library (likely uses React state/context)
- No data fetching library (likely raw fetch)
- No UI component library
- TypeScript for type safety
- Server-side rendering via Next.js

The frontend is clearly secondary to the backend. It provides visibility into incidents, approvals, and evaluation results but is not the primary interface for the system.

---

## 15. Concurrency and Async Systems

### Async Model

The API server is fully async (FastAPI + uvicorn). Database operations use SQLAlchemy async sessions. HTTP calls to LLM providers use httpx AsyncClient. Redis operations use redis.asyncio.

### Celery-Async Bridge

Celery tasks are synchronous by design. The bridge pattern:
```python
@celery_app.task
def run_incident_pipeline(incident_id: str) -> None:
    run_async(_run_incident_pipeline(UUID(incident_id)))
```

`run_async()` creates a new event loop per task execution. This is safe because Celery workers are process-based (not thread-based), so each task gets its own process with its own event loop.

### Parallel Fan-Out

LangGraph's `Send` mechanism dispatches metrics, logs, and deployment evidence gathering in parallel. All three run concurrently and their results converge at the root_cause_analysis node (LangGraph handles the join automatically).

### Heartbeat Monitoring

The incident pipeline task runs a background `asyncio.Task` that updates `pending_tasks.updated_at` every 5 seconds. The replay scheduler considers tasks "stale" if no heartbeat for 20 seconds, enabling detection of crashed workers.

### Race Condition Prevention

- `task_acks_late=True` + `reject_on_worker_lost=True`: If a worker crashes mid-task, the message is redelivered to another worker
- `worker_prefetch_multiplier=1`: Workers only take one task at a time, preventing starvation
- `lease_owner` in pending_tasks: Only the worker holding the lease can heartbeat, preventing duplicate execution
- Atomic evidence replacement: DELETE + INSERT in single transaction prevents partial state

### Retry Logic

Three levels of retry:
1. **LLM provider**: 2 retries with exponential backoff per provider (in provider_chain)
2. **Celery task**: 3 retries with exponential backoff (autoretry_for)
3. **Replay scheduler**: Re-enqueues stale tasks up to 5 times before dead-lettering

### Backpressure

- `worker_prefetch_multiplier=1` prevents queue buildup in worker memory
- `task_soft_time_limit=300` (5 min) raises SoftTimeLimitExceeded
- `task_time_limit=360` (6 min) hard-kills the task
- Dead-letter after 5 replay attempts prevents infinite retry loops

---

## 16. Security Review

### Authentication

JWT tokens validated against Auth0 configuration. In development, uses HS256 symmetric key. The middleware extracts roles from the token and attaches them to the request context.

**Weakness**: The development JWT in docker-compose.yml (`NEXT_PUBLIC_DEMO_BEARER_TOKEN`) is a hardcoded token with admin/operator/viewer roles. If this leaks to production, it grants full access.

### Authorization

Role-based: admin > operator > viewer. Each endpoint declares minimum required role via `require_role()` dependency.

### Tool Execution Safety

Multi-layer defense:
1. **Allowlist**: Only tools in `tool_allowlist.yaml` can execute
2. **Risk classification**: Actions classified into READ_ONLY/SAFE_MUTATION/HIGH_RISK/DESTRUCTIVE
3. **Approval tokens**: Dangerous tools require a JWT scoped to specific incident + actions
4. **Audit logging**: Every tool execution (authorized or blocked) is logged

### Secrets Management

- Secrets in `.env` file (not committed to git via .gitignore)
- Production validation: startup fails if default secrets detected
- Approval tokens use separate secret from auth tokens (defense in depth)

### Vulnerabilities

1. `python-jose` is unmaintained — potential unpatched JWT vulnerabilities
2. No rate limiting on the webhook endpoint (configured but not enforced in code)
3. No input sanitization on alert payload content stored in JSONB
4. The `tool_allowlist.yaml` is read from filesystem — if an attacker can write to that path, they can allowlist dangerous tools
5. Celery accepts only JSON serialization (good — prevents pickle deserialization attacks)

---

## 17. Performance Engineering

### Latency-Sensitive Paths

1. **Webhook ingestion**: Should be <100ms. Currently: DB write + Redis enqueue. Acceptable.
2. **Router classification**: LLM call dominates (500ms-5s depending on provider). Mitigated by LLM response cache.
3. **Evidence gathering**: Three parallel LLM calls. Wall-clock time = max(metrics, logs, deployment).
4. **Root cause analysis**: Algorithmic, no LLM. Should be <50ms for typical evidence sets.

### Caching

- **LLM response cache** (`memory/short_term/llm_cache.py`): In-process dict keyed by SHA256 of request payload. Prevents duplicate LLM calls for identical inputs. Lost on process restart.
- **Redis incident state**: 1-hour TTL. Avoids PostgreSQL reads for graph state during node transitions.
- **Settings**: `@lru_cache` on `get_settings()`. Single load per process lifetime.

### N+1 Concerns

- `selectinload` on incident relationships prevents N+1 for agent_executions, evidence_items, remediation_actions
- However, `list()` endpoint loads all incidents without pagination — will degrade with scale

### Scaling Bottlenecks

1. **Single Celery worker**: Default configuration runs one worker. Under load, incidents queue up.
2. **In-process LLM cache**: Not shared across workers. Each worker builds its own cache.
3. **PostgreSQL connections**: No connection pooling configuration visible. Each async session creates a connection.
4. **Qdrant**: No connection pooling. Each retrieval creates a new HTTP client.

---

## 18. Error Handling Philosophy

### Graceful Degradation

The system is designed to continue operating under partial failure:
- Redis unavailable → `save_state()` returns False, pipeline continues without cache
- Qdrant unavailable → similar incident search returns empty, classification still works
- LLM providers fail → deterministic fallback classifier activates
- Celery unavailable → task stored in pending_tasks table for later replay

### Failure Transparency

Every failure is recorded:
- Provider attempts logged with error details
- Operating mode transitions logged
- Dead-letter tasks include failure reason
- Audit log captures blocked tool executions
- Graph state includes `fallback_activated` and `provider_chain_result`

### Logging Quality

Structured JSON logging via structlog with context variables (request_id, incident_id, thread_id, agent). Every significant event has a named log event with typed fields. This enables log-based alerting and debugging.

### Operational Resilience

- Heartbeat monitoring detects crashed workers within 20 seconds
- Replay scheduler re-enqueues stale tasks every 10 seconds
- Dead-letter queue prevents infinite retry loops
- Approval timeout auto-rejects after 30 minutes (prevents stuck incidents)

---

## 19. Testing Strategy

### Test Categories

| Category | Count | Purpose |
|----------|-------|---------|
| Unit | ~400+ | Individual function/class behavior |
| Integration | ~50+ | API endpoint + DB interaction |
| Evaluation | ~200+ | Benchmark scoring, calibration, decision quality |
| Chaos | ~50+ | Broker outage, crash recovery, state corruption |
| Orchestration | ~50+ | Async stability, concurrency, worker recovery |
| Production | ~100+ | Infrastructure resilience, observability, security |
| Resilience | 45 | Circuit breaker, provider chain, operating modes |
| Replay | ~50+ | Chaos replay, concurrency replay |
| Runtime | ~50+ | Runtime validation |

**Total**: 1473 passing, 1 known failing.

### Testing Philosophy

1. **Evaluation tests are the most important**: They prove the system measures its own weaknesses correctly
2. **Chaos tests prove resilience**: Broker outage, state corruption, crash recovery
3. **No mocking of the evaluation framework itself**: The evaluation runner executes real agent code
4. **Deterministic replay**: Same inputs always produce same outputs (seeded RNG, fixed timestamps)

### What Is Well-Tested

- Fallback classifier (11 tests covering all categories + edge cases)
- Circuit breaker state transitions
- Provider chain failover behavior
- Evaluation integrity (golden label isolation)
- Remediation safety scoring
- Operator trust scoring
- Causal ambiguity resolution

### What Is Dangerously Untested

- Live LLM integration (all tests use mocked clients)
- Actual Qdrant vector search quality
- Real Prometheus/Loki/GitHub tool execution
- WebSocket streaming behavior
- Frontend functionality (no frontend tests)
- Database migration path (no Alembic tests)
- Load behavior under concurrent incidents

---

## 20. CI/CD and DevOps

### Pipeline Structure

**CI (every push/PR)**:
1. Ruff linting (fast, catches style + import issues)
2. pytest unit + integration tests
3. Evaluation count check (verifies benchmark runs)
4. Frontend build (Next.js compilation)

**Evaluation (every push/PR)**:
1. Full evaluation summary (runs all 121 benchmark incidents)

**Deploy (main branch only)**:
1. Build API Docker image
2. Build web Docker image
3. No push to registry, no actual deployment

### Gaps

- No container registry push
- No staging environment
- No production deployment automation
- No database migration step in CI
- No load testing in CI
- No security scanning (SAST/DAST)
- No dependency vulnerability checking

### Operational Risks

- The deploy pipeline builds images but doesn't deploy them anywhere
- No rollback mechanism defined
- No health check verification after deployment
- No canary or blue-green deployment strategy

---

## 21. Code Quality Assessment

### Strengths

- Consistent use of type hints throughout
- Pydantic models for all data boundaries
- Repository pattern provides clean separation
- Structured logging with context propagation
- Explicit error handling with typed exceptions
- Well-documented modules (docstrings explain WHY, not just WHAT)

### Weaknesses

- Some files are very long (orchestration_runner.py ~350 lines, incident_repo.py ~250 lines)
- The `_DEFAULT_REMEDIATION_HISTORY` is hardcoded in multiple places (risk_agent and orchestration_runner)
- Global mutable state (`_GRAPH`, `_PROVIDER_CHAIN`, `_FALLBACK_CLASSIFIER` singletons)
- The `run_async()` bridge between Celery and asyncio is a known anti-pattern

### Technical Debt

1. No Alembic migrations — schema changes require manual intervention
2. `python-jose` should be replaced with `PyJWT`
3. LangGraph version is old and will need upgrading
4. In-process LLM cache should be Redis-backed for multi-worker sharing
5. The `tool_allowlist.yaml` is read from disk on every execution

---

## 22. Scaling Analysis

### What Breaks First

1. **Single Celery worker**: Under burst load, incidents queue up. Fix: scale workers horizontally.
2. **In-process LLM cache**: Each worker has its own cache. Fix: move to Redis-backed cache.
3. **PostgreSQL connections**: No pooling. Fix: add PgBouncer or configure pool_size.
4. **LLM provider rate limits**: The circuit breaker helps but doesn't prevent 429s. Fix: request queuing with token bucket.

### Horizontal Scaling Readiness

- API server: Stateless, can scale horizontally behind a load balancer
- Celery workers: Can scale horizontally (Redis broker handles distribution)
- PostgreSQL: Single instance, would need read replicas for read-heavy workloads
- Redis: Single instance, would need Redis Cluster for high throughput
- Qdrant: Single instance, would need sharding for large vector collections

### Operational Limits

- LangGraph MemorySaver is in-process only — interrupt/resume doesn't work across workers
- The `@lru_cache` settings pattern means config changes require full restart
- The singleton graph (`_GRAPH`) means graph recompilation requires process restart

---

## 23. Maintainability Review

### Onboarding Difficulty

**Medium-High**. A new engineer needs to understand:
- LangGraph StateGraph semantics (nodes, edges, Send, interrupt)
- The evaluation integrity model (golden label isolation)
- The resilience layer (provider chain, circuit breakers, operating modes)
- The Celery-async bridge pattern
- The repository pattern with SQLAlchemy async

The codebase is well-structured and documented, but the domain complexity (probabilistic reasoning, causal graphs, uncertainty quantification) requires significant ramp-up time.

### Cognitive Complexity

The highest complexity is in:
1. `orchestration_runner.py` — 7-step pipeline with multiple agent invocations
2. `probabilistic_reasoner.py` — uncertainty engine with temperature scaling
3. `incident_pipeline.py` — heartbeat monitoring, dead-letter handling, replay logic
4. `provider_chain.py` — multi-layer failover with circuit breakers

### Documentation Quality

Good. Module-level docstrings explain purpose and constraints. The README is honest about limitations. Architecture decision records exist in `docs/adr/`. The evaluation framework has explicit integrity contracts.

---

## 24. Architectural Strengths

1. **Evaluation integrity enforcement**: The Phase 40 fix (golden label isolation) is genuinely important. Most AI projects never discover this flaw.

2. **Explicit operating modes**: The five-mode system with automatic transitions is a mature pattern rarely seen in research projects.

3. **Safety-first execution**: The multi-layer tool execution guard (allowlist → risk tier → approval token → audit log) is production-quality.

4. **Failure transparency**: The system never silently fails. Every provider attempt, mode transition, and fallback activation is recorded.

5. **Deterministic evaluation**: Seeded RNG, fixed timestamps, and mocked infrastructure enable reproducible benchmarks.

6. **Separation of evaluation from runtime**: The `ExecutionMode` enum with runtime assertions prevents accidental production side effects during evaluation.

7. **Celery configuration**: `acks_late`, `reject_on_worker_lost`, `prefetch_multiplier=1`, time limits, and dead-letter handling represent battle-tested patterns.

---

## 25. Architectural Weaknesses

1. **Root-cause accuracy (0.0820)**: The core value proposition (automated RCA) doesn't work well. Heuristic candidate generation is too shallow.

2. **No durable cross-process checkpointing**: LangGraph uses MemorySaver (in-process). If a worker crashes mid-pipeline, the graph state is lost. The custom WorkflowCheckpointStore writes snapshots but isn't integrated with LangGraph's resume mechanism.

3. **Hardcoded remediation history**: `_DEFAULT_REMEDIATION_HISTORY` appears in multiple files. Should be loaded from database.

4. **Static topology**: The 4-service topology in `topology.yaml` doesn't reflect the 17 services referenced in benchmarks. Blast-radius estimation is unrealistic.

5. **No schema migrations**: `create_all()` works for development but is dangerous in production (can't evolve schema without data loss).

6. **LLM cache is in-process**: Not shared across workers. Under load, each worker makes redundant LLM calls.

7. **No pagination**: The incidents list endpoint returns all incidents. Will degrade with scale.

8. **Singleton pattern for graph**: `_GRAPH` global means the graph can't be reconfigured without process restart. The `reset_graph()` function exists but is a workaround.

---

## 26. Refactor Recommendations

### Priority 1: Critical

1. **Add Alembic migrations** — Required before any production deployment. Impact: high. Complexity: medium.

2. **Replace python-jose with PyJWT** — Security risk from unmaintained dependency. Impact: medium. Complexity: low.

3. **Add database connection pooling** — Configure `pool_size` and `max_overflow` on the async engine. Impact: high under load. Complexity: low.

### Priority 2: Important

4. **Move LLM cache to Redis** — Share cache across workers. Impact: reduces LLM costs and latency. Complexity: medium.

5. **Add pagination to list endpoints** — Prevent unbounded queries. Impact: prevents degradation at scale. Complexity: low.

6. **Install langgraph-checkpoint-postgres** — Enable cross-process interrupt/resume. Impact: enables multi-worker approval flows. Complexity: medium.

7. **Extract remediation history to database** — Remove hardcoded defaults. Impact: enables learning from real outcomes. Complexity: low.

### Priority 3: Improvement

8. **Add SAST/dependency scanning to CI** — Catch vulnerabilities early. Complexity: low.

9. **Add load testing** — Understand scaling limits. Complexity: medium.

10. **Improve root-cause candidate generation** — Replace keyword matching with learned patterns. Impact: core quality improvement. Complexity: high.

---

## 27. Future Evolution Path

### Near-Term (3-6 months)

- Add Alembic migrations and production deployment pipeline
- Integrate real Prometheus/Loki queries (replace mocked evidence agents)
- Improve root-cause accuracy through better candidate generation
- Add operator feedback loop (capture override decisions, feed back into retrieval)

### Medium-Term (6-12 months)

- Replace heuristic RCA with learned causal models (Bayesian networks or GNNs over service graphs)
- Add multi-tenant support (organization-scoped incidents and configurations)
- Implement real-time streaming RCA (process events as they arrive, not batch)
- Add A/B testing framework for reasoning improvements

### Long-Term (12+ months)

- Graduated autonomy (system earns trust through demonstrated accuracy)
- Cross-cluster incident correlation
- Predictive incident detection (anomaly detection before alerts fire)
- Self-improving retrieval (learn which historical incidents are actually useful)

### Architecture Changes Eventually Needed

1. **Event sourcing for incidents**: As the system processes more incidents, the append-only execution log becomes the primary data model. Event sourcing would be natural.
2. **Separate read/write models (CQRS)**: The dashboard reads different data shapes than the pipeline writes. Separate models would improve both.
3. **Service mesh integration**: Direct integration with Istio/Envoy for real-time topology discovery instead of static YAML.

---

## 28. Learning Notes for Engineers

### Key Lessons

1. **Evaluation integrity is harder than it looks**: The Phase 40 discovery (golden label leakage) is a common trap in AI systems. Always verify that your evaluation measures actual system behavior, not a tautology.

2. **Determinism enables testing**: The algorithmic root-cause path (no LLM) is testable precisely because it's deterministic. The tradeoff is lower quality, but at least you can measure the quality.

3. **Operating modes are underrated**: Most systems are either "working" or "broken." Explicit degraded modes let you continue providing value under partial failure.

4. **Circuit breakers need per-provider granularity**: A single global circuit breaker would disable all providers when one fails. Per-provider breakers allow graceful failover.

5. **Celery configuration matters enormously**: The difference between `acks_late=True` and the default is the difference between crash recovery and data loss.

6. **JWT scoping prevents privilege escalation**: Approval tokens scoped to specific incident + action IDs prevent an operator from approving actions on a different incident.

7. **The fallback classifier is the most reliable component**: Zero dependencies, deterministic, fast. It will never fail. This is the foundation of the resilience model.

### Anti-Patterns to Avoid

1. **Don't use `asyncio.run()` in production code** — It creates a new event loop. The Celery bridge is acceptable because each task is isolated, but don't do this in the API server.

2. **Don't cache settings with `@lru_cache` if you need hot-reload** — This pattern is fine for immutable config but prevents runtime reconfiguration.

3. **Don't use `latest` Docker tags** — Builds become non-reproducible. Pin versions.

4. **Don't store secrets in docker-compose environment blocks** — The demo JWT token in docker-compose.yml is a security risk if the file is deployed.

---

## 29. Glossary

| Term | Definition |
|------|-----------|
| **Agent** | A self-contained reasoning module that processes incident data and produces structured output |
| **Agent Loop** | The generic tool-calling cycle: LLM generates tool calls → tools execute → results fed back → LLM produces final output |
| **Blast Radius** | Estimated number of users/services affected by an incident, computed via topology traversal + Monte Carlo |
| **Calibration** | How well confidence scores match actual accuracy. ECE measures the gap. |
| **Circuit Breaker** | Per-provider state machine that prevents calls to known-failing providers |
| **Deterministic Fallback** | Zero-dependency keyword classifier that activates when all LLM providers fail |
| **ECE** | Expected Calibration Error. Lower is better. Measures confidence-accuracy alignment. |
| **Evidence Item** | A normalized piece of evidence (metric, log entry, deployment record) stored in PostgreSQL |
| **Golden Label** | The ground-truth answer in the benchmark suite. Used only for scoring, never for agent input. |
| **Graph State** | The TypedDict that flows through LangGraph nodes, accumulating results |
| **Grounding Score** | Measures whether agent claims are supported by retrieved evidence |
| **Hallucination** | A causal claim that violates topology, temporal, or deployment constraints |
| **Hybrid Retrieval** | Vector search + topology boost + temporal decay for re-ranking results |
| **Interrupt** | LangGraph mechanism to pause graph execution (used for approval gates) |
| **Operating Mode** | One of FULL/DEGRADED/LOCAL_ONLY/SAFE_MODE/OBSERVE_ONLY |
| **Pending Task** | A deferred pipeline execution stored in PostgreSQL when Celery is unavailable |
| **Provider Chain** | Multi-layer LLM failover: primary → secondary → local → deterministic |
| **Replay** | Re-enqueuing a stale or failed task for another execution attempt |
| **Risk Tier** | Classification of remediation actions: READ_ONLY/SAFE_MUTATION/HIGH_RISK/DESTRUCTIVE |
| **Router** | The first agent in the pipeline that classifies incident type and severity |
| **Send** | LangGraph mechanism for parallel fan-out to multiple nodes |
| **Triage** | Human escalation path when classification confidence is below 0.6 |
| **UncertaintyEngine** | Component that assesses evidence quality, distributes probability, and recommends escalation |
| **Underconfidence** | When the system's confidence is lower than its actual accuracy (87.5% of cases) |
