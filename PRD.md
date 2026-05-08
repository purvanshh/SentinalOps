# SentinelOps AI — Product Requirements Document (v2.0)

**Autonomous Multi-Agent Incident Response & Reliability Orchestration Platform**

---

## 1. Product Vision & Strategic Intent

SentinelOps AI is a production-grade, autonomous incident investigation and remediation platform. It transforms raw monitoring signals into trustworthy, actionable insights through a coordinated, durable, and transparent multi-agent system. The platform is not a wrap‑around chatbot, not a trivial RAG pipeline, and not a linear workflow. It is a **stateful, tool‑augmented reasoning engine** that mimics how the best SREs investigate incidents: gathering heterogeneous evidence, cross‑checking hypotheses against physical constraints, quantifying risk, and only then acting — always with human oversight for safety‑critical decisions.

The project’s dual ambition is to serve as both a realistic enterprise AI Ops prototype and a complete educational framework covering every facet of modern AI engineering: agent decomposition, tool use, pragmatic retrieval, durable orchestration, evaluation, and responsible deployment.

---

## 2. Core Problem Statement

Production environments continuously generate logs, metrics, traces, and deployment events. When something fails, engineers must manually:

- Correlate disparate signals across hours of data.
- Remember or look up recent changes.
- Mentally simulate causal chains to identify the most likely root cause.
- Estimate the blast radius and risk of various mitigations.
- Write a coherent postmortem after the fact.

The result is high Mean Time to Resolution (MTTR), operator fatigue, inconsistent investigations, and incomplete institutional memory. Existing observability tools surface alerts; they do not perform structured, evidence‑grounded reasoning. SentinelOps AI fills this gap with an agentic system that:

1. **Investigates** by autonomously gathering and cross‑referencing telemetry.
2. **Reasons** about causality using explicit evidence chains.
3. **Quantifies** risk and blast radius with data‑driven models.
4. **Proposes** safe remediations, pausing for human approval when necessary.
5. **Generates** rich, traceable postmortems that improve over time.

---

## 3. Product Goals

| # | Goal | Success Criteria |
|---|------|-----------------|
| 1 | **Autonomous multi‑step investigation** | >90% of synthetic incidents see all relevant data sources queried without human prompt |
| 2 | **Evidence‑grounded root cause analysis** | <5% hallucination rate on a golden dataset; each causal claim cites specific, verifiable evidence |
| 3 | **Coordinated, durable orchestration** | Graph survives 100% of injected node restarts and network drops without manual intervention |
| 4 | **Human‑in‑the‑loop safety** | No high‑risk action executes without explicit approval; approval timeout escalation works within 5 minutes |
| 5 | **Quantified risk and blast radius** | Estimated blast radius (services users) is within 30% of ground truth in 80% of test cases |
| 6 | **Transparent, evaluatable outputs** | Every agent step is logged, traceable, and evaluable against a curated evaluation harness |
| 7 | **Continuous improvement through evaluation** | RMTR, hallucination, and safety metrics tracked per release; no regression |

---

## 4. Non-Goals

- A generic chatbot or natural‑language Q&A system
- A ticketing or IT service management (ITSM) replacement
- A Kubernetes management plane (though it interfaces with container APIs)
- Replacing human incident commanders – the platform augments, never replaces
- Executing irreversible actions without human approval (e.g., database failover)
- Acting outside configured permission boundaries

---

## 5. High‑Level User Flow

1. **Trigger** – Prometheus alert fires: “API latency > 2s for 5 minutes.”
2. **Ingest** – Incident object created; webhook enters the orchestration engine.
3. **Classify** – Router Agent tags incident as `database‑latency / sev:critical`.
4. **Parallel evidence gathering** – Metrics Agent, Logs Agent, and Deployment Agent fetch data simultaneously.
5. **Root Cause Reasoning** – Root Cause Agent consumes all evidence, builds a structured causal graph, generates ranked hypotheses with evidence‑for/against.
6. **Risk Assessment** – Risk Agent computes blast radius (services, users, revenue impact) and risks of candidate mitigations.
7. **Remediation Proposal** – Remediation Agent drafts action plan; actions tagged with `requires_approval`.
8. **Human Approval** – Approval Agent pauses the workflow, notifies on‑call; plan reviewed via UI or Slack.
9. **Execution & Verification** – Approved actions run; post‑execution metrics/ logs re‑checked to confirm mitigation.
10. **Postmortem Generation** – Postmortem Agent constructs a complete timeline, root cause analysis, contributing factors, detection gaps, and prioritized prevention items.
11. **Evaluation & Archival** – Entire trace, agent decisions, and evaluation scores stored for audit and learning.

---

## 6. System Architecture (Deep Dive)

```
┌──────────────────────────────────────────┐
│           Frontend (Next.js)              │
│  Incident board, Agent trace, Approval    │
└───────────────┬──────────────────────────┘
                │
┌───────────────▼──────────────────────────┐
│       API Gateway (FastAPI + Auth0)       │
│  - JWT auth, RBAC, session, websockets   │
└───────────────┬──────────────────────────┘
                │
┌───────────────▼──────────────────────────┐
│  LangGraph Orchestrator (StateGraph)      │
│  - Nodes: Agent nodes, tool nodes,        │
│    human-interrupt nodes, eval nodes      │
│  - Durable: checkpointing to PG/Redis    │
│  - Conditional edges, parallelism, retries│
└───┬──────────────┬──────────────┬───────┘
    │              │              │
┌───▼──┐  ┌───────▼──────┐ ┌────▼──────────┐
│Agents│  │Shared State  │ │Evaluation     │
│Pool  │  │(Redis + PG)  │ │Module         │
└───┬──┘  └──────────────┘ └───────────────┘
    │
┌───▼──────────────────────────────────────┐
│       Tool Integration Layer              │
│ - Prometheus, Loki, Grafana APIs          │
│ - GitHub/GitLab (deploy history)          │
│ - Docker / Kubernetes (limited actions)   │
│ - Slack, PagerDuty (notifications)        │
│ - Qdrant (RAG for past incidents, runbooks)│
└──────────────────────────────────────────┘
```

The orchestrator operates as a deterministic state machine where each agent is a callable node that receives the current `IncidentState` and returns an updated state. `IncidentState` is a typed dictionary checkpointed after every node. The entire graph is resumable from the last successful checkpoint.

**Key architectural choices**:
- **Agent isolation**: each agent’s system prompt, tools, and output schema are independently testable.
- **Evidence‑first data flow**: agents that directly query telemetry (Metrics, Logs, Deployment) produce structured summaries; subsequent reasoning agents (Root Cause, Risk) are forbidden from making live queries — they must work exclusively from the summaries. This prevents iterative chasing of random correlations and forces rigorous citation.
- **RAG only for static knowledge**: live telemetry is never injected via retrieval vector search; it is always a real‑time API call.
- **Human interrupt as a first‑class LangGraph node**: not an ad‑hoc API flag.

---

## 7. Agent System – Detailed Specifications

Every agent is defined by:
- **Role** – clear responsibility
- **Input** – part of `IncidentState`
- **Tools** – allowed tool signatures
- **Output** – typed structure merged back into state
- **Safety constraints** – data access, side‑effect guarantees

The core model is NVIDIA GPT‑OSS‑120B, served via NIM with OpenAI‑compatible API. This model is preferred for its strong reasoning, very low cost, and native tool calling. In a future cost‑optimization layer, smaller models may handle classification tasks.

---

### 7.1 Router Agent

**Goal**: Transform a raw alert into a typed incident classification and determine initial investigation path.

**Input**:
- Alert payload (JSON from Prometheus/Grafana)
- Optional: recent incident history (RAG top‑3 similar incidents)

**Output**:
```json
{
  "incident_type": "database_latency",
  "severity": "critical",
  "confidence": 0.91,
  "requires_immediate_investigation": true,
  "recommended_workflow": "full_investigation",
  "rationale": "Latency spike in payment service correlates with database connection pool exhaustion pattern observed in past incidents INC034, INC078."
}
```

**Tool use**: None. Classification is a pure LLM completion with structured output. The prompt includes few‑shot examples of alert‑to‑type mappings and explicitly instructs the model to output `"confidence"` and `"rationale"`.

**Fallback**: If confidence < 0.6 or `incident_type` is `"unknown"`, the workflow branches to a human triage step (message to Slack) and pauses.

---

### 7.2 Metrics Agent

**Goal**: Fetch relevant Prometheus metrics within a time window around the incident, and return a concise, data‑driven summary.

**Tools**:
- `query_prometheus(promql, start, end, step) → DataFrame`
- `get_service_dependencies(service) → list[ServiceNode]`

**Output**:
```json
{
  "summary": "CPU on payment-api spiked from 40% to 98% at 14:03 UTC. Connection pool utilization reached 100% at 14:04. Database query latency (p99) increased from 50ms to 900ms.",
  "anomalies": [
    {
      "metric": "node_cpu_seconds_total",
      "observed": "98%",
      "expected_range": "30-50%",
      "z_score": 5.2
    }
  ],
  "correlation_hints": [
    "CPU spike coincides exactly with deployment event DEP-4351"
  ],
  "raw_query_links": ["https://prometheus.example.com/..."]
}
```

**Safety**: Read‑only. Queries are restricted to a pre‑approved list of PromQL templates to prevent overly broad queries that could overload Prometheus.

---

### 7.3 Logs Agent

**Goal**: Search Loki for error patterns, stack traces, and temporal correlations.

**Tools**:
- `query_loki(logql, start, end) → list[LogEntry]`
- `expand_log_context(trace_id) → list[LogEntry]`
- `extract_stacktrace(log_entry) → str`

**Output**:
```json
{
  "error_signatures": [
    {
      "signature": "java.sql.SQLTimeoutException: Connection pool exhausted",
      "count": 1423,
      "first_seen": "14:03:01",
      "sample": "...",
      "trace_ids": ["abc123", "def456"]
    }
  ],
  "temporal_correlations": [
    {
      "event": "deployment v2.3.1 completed",
      "timestamp": "14:02:55",
      "relation": "5 seconds before first error"
    }
  ]
}
```

**Safety**: Queries are time‑bounded and scoped to the affected service to avoid returning millions of logs.

---

### 7.4 Deployment Agent

**Goal**: List recent deployments and infrastructure changes, compute risk scores for each.

**Tools**:
- `get_recent_deployments(service, hours=24) → list[Deployment]`
- `get_commit_diff(repo, commit_sha) → str` (summarized via LLM later)
- `get_rollback_candidates(service) → list[Deployment]`

**Output**:
```json
{
  "recent_changes": [
    {
      "deployment_id": "DEP-4351",
      "service": "payment-api",
      "version": "v2.3.1",
      "time": "14:02:55",
      "commit_summary": "Refactored connection pool from HikariCP to custom pool",
      "risk_score": 0.85
    }
  ],
  "correlation_with_incident": "Deployment finished 10 seconds before latency spike; connection pool code is primary suspect"
}
```

**Risk score model**: A simple heuristic based on change type (e.g., infrastructure change scores higher than HTML fix), time since deploy, and whether similar changes caused past incidents (retrieved via RAG from incident DB).

---

### 7.5 Root Cause Agent – Comprehensive Hallucination Mitigation

This is the intellectual core of the system. The Root Cause Agent must synthesise evidence from Metrics, Logs, and Deployment agents, then produce a **ranked set of evidence‑grounded hypotheses**. It must **never** fabricate connections. The design below makes hallucination structurally difficult.

#### 7.5.1 Input
- Structured outputs from Metrics, Logs, Deployment agents.
- Service dependency graph (from topology DB).
- Incident timeline (constructed from agent traces).
- (Optional) Top‑3 similar past incidents from RAG (only for pattern suggestion, not evidence substitution).

#### 7.5.2 Internal Reasoning Architecture
The Root Cause Agent is itself a **mini multi‑step pipeline** composed of:
1. **Evidence Normalizer** – converts all agent outputs into a uniform set of timed events (`EvidenceItem`), each with source, timestamp, and confidence.
2. **Causal Graph Builder** – uses the service dependency map and a simple physics‑of‑IT model (e.g., downstream services can only be affected after the upstream dependency) to construct a feasible causal graph.
3. **Hypothesis Generator** – proposes candidate root causes by aligning evidence with known failure patterns (from a curated pattern library, not free‑form hallucination).
4. **Deductive Tester** – for each hypothesis, applies a rigorous “must‑have” / “must‑not‑have” evidence test.
5. **Ranker** – scores hypotheses by evidence coverage, temporal consistency, and prior probability from historical data.

All steps are **deterministic where possible** and **LLM‑augmented only for synthesis of natural language rationales**. The LLM never decides which hypothesis is correct; it merely formats the results of the algorithmic tests.

#### 7.5.3 Key Anti‑Hallucination Mechanisms

**A. Evidence Grounding via Required Citations**
Every hypothesis must explicitly cite at least one `EvidenceItem` per claim. Output schema:
```json
{
  "hypothesis": "Connection pool exhaustion caused by incorrect pool size in v2.3.1",
  "confidence": 0.87,
  "evidence_for": [
    {"item_id": "E1", "description": "CPU spike on payment-api", "source": "metrics_agent"},
    {"item_id": "E3", "description": "Connection pool error in logs", "source": "logs_agent"}
  ],
  "evidence_against": [],
  "evidence_neutral": [],
  "causal_chain": "DEP-4351 → connection pool config change → pool exhaustion → thread contention → high CPU → latency increase on API",
  "counterfactual_test": "If the pool config were correct, we would not expect pool exhaustion errors, but we see 1423 such errors."
}
```
The evidence items are traceable IDs that resolve to exact data points; the UI can display them inline. This makes ungrounded statements immediately visible.

**B. Temporal Consistency Enforcer**
A rule‑based pre‑processor checks that no evidence item is cited for a causal relationship if the alleged effect occurred *before* the cause. The LLM is instructed to reject any hypothesis that violates temporal ordering.

**C. Physically Impossible Causal Path Detection**
Using the service dependency graph, the system automatically eliminates hypotheses that propose a root cause in a service that has no dependency path to the observed symptom (e.g., “database failure caused issue in frontend” when the frontend only calls the API, which in turn calls the database, the symptom is frontend; that path is possible, but if the dependency graph shows no connection, the hypothesis is rejected). The graph is stored in Postgres and loaded at inference time.

**D. Pattern Library (Retrieval‑Guided, Not Retrieval‑Decided)**
A curated set of ~50 known failure patterns (e.g., “thread pool exhaustion”, “OOMKill → restart loop”, “slow downstream → connection timeout”) is stored as structured JSON. During hypothesis generation, the system retrieves the top‑k patterns (via Qdrant embedding match on the evidence summary) and uses them to *suggest* candidate causes, but the causal chain must still be built from actual evidence. The retrieved patterns are inserted as “hints” with a clear label: `pattern_suggestion: “connection_pool_exhaustion (match_score: 0.82)”`. This prevents the LLM from inventing patterns it hasn’t seen and grounds it in known failure domains.

**E. Confidence Score Decomposition**
Confidence is not an opaque LLM output. It is computed as a weighted average of:
- `evidence_coverage` (fraction of explained anomalies)
- `temporal_score` (all events in correct order)
- `pattern_match_score` (from retrieval)
- `prior_probability` (base rate of this cause from incident history in PostgreSQL)
- `counterfactual_power` (how well the hypothesis explains both what is and what is not observed)

The formula: `C = 0.3*cov + 0.2*temp + 0.2*pattern + 0.15*prior + 0.15*counterfact`
These weights are configurable and tuned via the evaluation harness. By making the score transparent, operators can understand *why* the system believes a certain cause, and thresholds can be set to require human review if confidence < 0.6.

**F. Explicit “Unknown” / “Insufficient Evidence” Output**
If no hypothesis reaches even a modest confidence threshold (default 0.4), the agent explicitly outputs:
```json
{
  "status": "insufficient_evidence",
  "possible_directions": ["Check network connectivity between API and DB", "Review recent configuration changes not captured by deployment agent"],
  "confidence": 0.12
}
```
This prevents the system from confidently espousing a wrong cause and signals the incident commander where the investigation is stuck.

**G. Multi‑Hypothesis Debate (Optional Stretch)**
For high‑stakes incidents (sev 0/1), the Root Cause Agent can spawn two internal “sub‑agents” that each argue for a different leading hypothesis, listing evidence for/against, then a “judge” sub‑agent selects the strongest one. This is implemented as a small sub‑graph within the agent node, using the same LLM but prompted to take adversarial roles. This further reduces individual LLM biases.

#### 7.5.4 Output Structure
```json
{
  "hypotheses": [ <list of hypothesis objects as above> ],
  "strongest_hypothesis_index": 0,
  "investigation_log": "Step1: built causal graph from 3 services; Step2: generated 2 hypotheses; ...",
  "recommended_next_steps": ["Check connection pool configuration", "Consider rolling back DEP-4351"]
}
```

The full `investigation_log` is stored for traceability and future training data.

#### 7.5.5 Evaluation Metrics Specific to Root Cause
- **Exact match of top‑1 hypothesis** with golden label (string comparison)
- **Correct service identified** (even if exact cause not fully detailed)
- **Evidence grounding score**: % of claims that can be traced to an ingested EvidenceItem
- **Temporal violation rate**: % of assessments where a cause‑effect pair is temporally reversed (should be 0)
- **Unknown‑when‑appropriate rate**: for synthetic incidents designed with insufficient data, the agent must output `insufficient_evidence`; we measure recall of this output.

---

### 7.6 Risk Assessment Agent – From Summaries to Quantitative Impact

The Risk Agent does not merely describe what is affected; it **quantifies the business impact** and **predicts the risk of candidate remediation actions**. This requires real data from service dependency graphs, request volume monitors, and historical incident impact databases.

#### 7.6.1 Inputs
- Root cause hypothesis (with affected service)
- Service dependency graph (from topology DB)
- Traffic metrics (requests per second to each service, from Prometheus)
- Historical incident impact data (user‑facing errors, from PostgreSQL)
- Candidate remediation actions (from next step)

#### 7.6.2 Internal Model

**A. Blast Radius Computation**
A deterministic graph traversal starting from the affected service(s). For each downstream service:
- Determine if it is critical (a boolean flag in topology DB).
- Multiply current traffic by a severity factor (from past incident data: if a similar incident caused 20% error rate, factor = 0.2).
- Sum estimated impacted requests and, if possible, map to users using a pre‑configured conversion (e.g., 1 unique user per 10 requests on average).

The output is not a single number; it is a distribution (using a simple Monte Carlo simulation with bounded ranges) to express uncertainty. This transforms “43,000 users impacted” into “40,000–46,000 users impacted (90% confidence)” — far more trustworthy.

**B. Remediation Risk Scoring**
For each proposed action:
- **Probability of failure**: estimated from execution history (we track past executions in a `remediation_history` table: success/failure rate).
- **Severity if failed**: e.g., rolling back a deployment is usually low‑risk, but restarting a stateful database may cause data loss or additional downtime.
- **Time to execute**: estimated from previous runs.
- **Compound risk score**: `R = P(failure) * Severity * (1 + ExecutionTime_factor)`.

These scores are computed via a rules engine (Python code) with default values (e.g., unknown action → high risk). The LLM is used only to interpret action descriptions and map them to known risk categories.

**C. User Impact Estimation**
If the incident is already affecting users, the agent fetches error rate from Prometheus or Loki and multiplies by traffic volume to estimate current user‑impacted count. For blast radius of new actions, it assumes the action might temporarily amplify the error rate.

#### 7.6.3 Output
```json
{
  "current_impact": {
    "error_rate": 0.23,
    "estimated_users_impacted_so_far": 12000,
    "trend": "increasing"
  },
  "blast_radius": {
    "affected_services": ["payment-api", "checkout"],
    "users_at_risk": {
      "mean": 43000,
      "p90": 46000,
      "description": "If payment-api continues erroring, downstream checkout will fail, affecting ~43k users."
    }
  },
  "remediation_risks": [
    {
      "action": "rollback DEP-4351",
      "probability_of_success": 0.95,
      "worst_case_impact": "brief 2‑second interruption during deployment switch",
      "risk_score": 0.08,
      "recommendation": "safe to proceed"
    },
    {
      "action": "restart payment-api",
      "probability_of_success": 0.70,
      "worst_case_impact": "could lose in‑flight transactions, data inconsistency risk",
      "risk_score": 0.65,
      "recommendation": "avoid unless rollback fails"
    }
  ]
}
```

**Evaluation**: For a test set of 20 known topology states and simulated incident impacts, we measure the absolute error of `users_at_risk.mean` compared to ground truth; we also measure the calibration of `probability_of_success` (Brier score).

This turns Risk Agent from a fancy summarizer into a **quantitative decision‑support system**.

---

### 7.7 Remediation Agent

(Keep original spec, but now it receives the risk‑scored actions and can choose among them based on least risk and highest success probability. It also includes a “verify” step after execution.)

**Additional tool**: `verify_metric(metric_name, expected_range)` — after executing an action, waits and checks if the metric returns to normal; if not, can escalate.

---

### 7.8 Postmortem Agent – Generating Institutional Knowledge, Not Just a Summary

A good postmortem is not a bland timeline; it is a **learning artifact** that identifies systemic weaknesses and actionable prevention items. The Postmortem Agent must go beyond concatenating agent outputs.

#### 7.8.1 Input
- Complete `IncidentState` (all agent outputs, timeline of actions, approvals)
- Raw incident timeline with timestamps and events (from LangGraph trace)
- Similar past incidents (RAG top‑5)
- Team’s postmortem template (customizable)
- Historical decisions and their outcomes (did a similar rollback work? was a restart risky?)

#### 7.8.2 Generation Process

**A. Structured Timeline Synthesis**
The agent constructs a multi‑column timeline:
- Time (UTC) | Event | Source | Impact | Mitigation
It does this automatically by parsing the checkpointed state and tool call logs. This is deterministic; no LLM needed.

**B. Root Cause Narrative**
Using the root cause hypothesis and evidence, the agent writes a concise narrative in the “5 Whys” style — but it must link each “Why” to a specific evidence item. The LLM is prompted to only repeat what is in the root cause analysis, not add new information. We enforce this by diffing the generated narrative against the root cause hypothesis’s evidence list and flagging any novel statements.

**C. Contributing Factors Analysis**
The postmortem must identify **latent failures** that allowed the incident to happen, not just the triggering event. We use a checklist (SRE‑proven) that the agent works through:
- Was monitoring adequate? (compare time of first symptom to alert trigger)
- Were deployment procedures followed? (check if deployment was rolled out gradually or all at once)
- Did the system have sufficient capacity? (compare peak usage to limits)
- Were recent changes tested adequately?
- Did any part of the system lack redundancy?

Each question is answered by querying relevant data (e.g., “compare deployment strategy from deployment agent output with best practice”). The agent outputs a table with each factor and a “detected” boolean.

**D. Action Items Generation**
Based on the contributing factors and root cause, the agent proposes preventative measures. It uses retrieval from a “previous action items” repository to avoid suggesting the same incomplete fix twice. For example, if a past incident already recommended “add connection pool monitoring” and that item was done, the system should not suggest it again without checking. We store a `prevention_items` table and verify status via API; the LLM is prompted to check that table before finalizing.

**E. Detection and Recovery Metrics**
Automatically compute:
- Time to Detect (TTD): alert timestamp – first anomaly timestamp.
- Time to Mitigate (TTM): time between alert and first effective remediation.
- Time to Resolve (TTR): total incident duration.
These are stored and tracked over time; the postmortem includes a chart of these metrics vs. previous incidents.

#### 7.8.3 Output
A Markdown document structured exactly to the team’s postmortem template, with sections:
- Summary
- Timeline
- Root Cause Analysis
- Contributing Factors
- Detection & Recovery Metrics
- Action Items (with owners and deadlines, if integrated with ticketing)
- Lessons Learned
- Appendices (agent trace, raw data)

The document is saved to PostgreSQL and optionally exported to Confluence/Notion via API.

#### 7.8.4 Quality Evaluation
We sample generated postmortems and have human reviewers rate them on:
- Completeness (are all sections filled without fabricated information)
- Actionability (are prevention items specific and practical)
- Accuracy (do the conclusions match the evidence)
This human feedback is used to fine‑tune the prompts.

---

## 8. Orchestration & State Management

The entire incident lifecycle is implemented as a LangGraph `StateGraph`. The state schema `IncidentState` is a typed dictionary that accumulates all agent outputs. Checkpoints are written to PostgreSQL after every node, allowing the workflow to resume precisely after any crash.

**Key orchestration features**:
- **Parallel fan‑out**: After classification, Metrics, Logs, and Deployment agents are called concurrently via `Send` API.
- **Conditional branching**: Based on severity and classification confidence, the graph can skip full investigation for low‑risk, well‑known patterns (e.g., a known transient network blip).
- **Human‑in‑the‑loop interrupts**: The Approval Agent node is marked `interrupt_before`. The graph pauses; the frontend or Slack bot polls for a decision, then resumes with an `Command` object appended to state.
- **Retries and fallbacks**: Tool calls are retried with exponential backoff (3 attempts). If an agent fails, a compensating fallback node logs a partial report and continues — the incident is not blocked by a single data source.
- **Recursion limit**: To avoid infinite loops from agent re‑prompting, a counter increments each time an agent re‑calls itself; after 2 re‑entries, the graph moves to a human escalation node.

---

## 9. Retrieval Augmented Generation (RAG) — Pragmatic Usage

RAG is applied exclusively where static, reference‑type knowledge aids reasoning:
- **Past incident summaries** → Qdrant embeddings; retrieved for Router classification hints and Root Cause pattern suggestion.
- **Operational runbooks** → indexed for access by Remediation Agent when proposing manual steps.
- **Service architecture docs** → used by Risk Agent to understand dependency criticality.

Live data (metrics, logs) never goes through RAG; it is fetched through direct tool calls. This prevents stale information and forces grounding.

---

## 10. Memory Architecture & Data Storage

**Short‑term (Incident) State**: The `IncidentState` object resides in Redis as a serialized blob while the graph is active; PostgreSQL checkpoints store historical snapshots.

**Long‑term Memory**:
- `incidents` table: status, severity, timestamps, final root cause.
- `agent_executions`: per‑agent step log with input, output, latency, tokens used, success/failure.
- `evidence_items`: every piece of telemetry cited by Root Cause Agent, with hash for fingerprinting.
- `remediation_actions`: action, approver, executed_at, result.
- `postmortems`: markdown content with versioning.
- `evaluations`: per‑incident metrics.

Vector store (Qdrant) collections:
- `past_incidents` (embedding of summary + alert type)
- `runbooks` (manual procedures)
- `prevention_items` (past action items to avoid duplication)

---

## 11. Evaluation System

A comprehensive evaluation harness enables continuous measurement and guard against regression.

**Test Dataset**: 75 synthetic incidents covering:
- Single‑service failures (OOM, CPU, latency)
- Deployment‑induced regressions
- Cascading failures (frontend → API → DB)
- Network partitions
- Insufficient‑data scenarios (to test “unknown” output)
- False‑positive alerts (metric spike without actual impact)

Each has a golden label: incident type, root cause, expected blast radius, correct remediation, and safe action.

**Metrics and Targets**:

| Metric | Target | Description |
|--------|--------|-------------|
| Classification Accuracy | >90% | Exact or fuzzy match of incident type |
| Root Cause Match (top‑1) | >75% | Hypothesis matches golden root cause string or equivalent |
| Evidence Grounding Score | >0.95 | Fraction of claims in RC output traceable to an EvidenceItem |
| Temporal Violation Rate | 0% | No cause after effect |
| Hallucination Rate | <5% | Statements not supported by any ingested evidence or pattern |
| Blast Radius MAE | <30% error | Mean absolute error of estimated users impacted vs ground truth |
| Remediation Safety | 100% | High‑risk actions never executed without approval in any run |
| Workflow Completion | >98% | Graph ends in terminal state without dead‑end or crash |
| Human Approval Latency | <15 min timeouts escalate | Works under load |

**Automated run**: The evaluation pipeline is triggered on each PR to the prompt or graph definition. It uses mocked tool responses to ensure reproducibility.

---

## 12. Security, Guardrails & Compliance

- **Authentication & Authorization**: JWT with Auth0; RBAC roles (viewer, operator, admin). Only operators can approve dangerous actions.
- **Tool‑Level Permissions**: Each tool definition includes a required `safety_level`. The orchestrator checks the current user’s level before executing. Even if the LLM hallucinates a tool call, the execution is blocked at the orchestrator layer.
- **Action Allowlisting**: In production environment configuration, certain tools (e.g., `restart_db`) may be completely disabled via config; the Agent never sees them in the tool list.
- **Audit Logging**: Every approval, rejection, tool call, and state change is logged to an immutable audit table.
- **Prompt Injection Defense**: System prompts contain explicit instructions to ignore any injected “ignore previous instructions” text; input sanitization strips markdown code blocks that could be misinterpreted as tool calls.
- **Data Privacy**: User data is never stored in prompts; only aggregated metrics and service identifiers.

---

## 13. Frontend Requirements (Deepened)

**Incident Command Center**:
- Real‑time status of active incidents with agent progress bar.
- Agent Trace Viewer: a tree visualization of the graph, each node expandable to show input/output, tool calls, latency.
- Approval Center: shows pending approvals with risk scores, evidence, and one‑click approve/reject.
- Evaluation Dashboard: historical MTTR, hallucination rates, agent performance trends.

**Key Interaction**: When a human approves, they can optionally add a note; the note is fed back into the state and can be used by Postmortem Agent.

---

## 14. Technology Stack & Infrastructure

| Component | Technology | Rationale |
|-----------|------------|-----------|
| API & server | FastAPI (async) | High performance, native OpenAPI doc |
| Orchestration | LangGraph 0.2+ | Durable graphs, checkpointing, interrupt support |
| LLM serving | NVIDIA NIM GPT‑OSS‑120B | Low‑cost, tool‑calling, OpenAI‑compatible; fallback to other OpenAI‑like endpoints |
| Task queue | Celery + Redis | For asynchronous tool calls (e.g., long Loki queries) |
| Database | PostgreSQL 15 | Checkpoints, incidents, evaluations, audit logs |
| Vector store | Qdrant | Runbooks, past incidents, pattern library |
| Observability | Prometheus, Loki, Tempo, Grafana | Full stack for the platform itself (meta‑observability) |
| Caching | Redis | State caching, session data |
| Frontend | Next.js 14 + Tailwind + React Flow | React Flow for graph visualization |
| Containerization | Docker Compose (dev), Kubernetes manifests (prod) | |
| Deployment | AWS ECS / Render / Railway | Easy, scalable; includes managed Postgres and Redis |

---

## 15. Failure Handling & Reliability

| Failure Scenario | Mitigation |
|------------------|------------|
| LLM timeout | Retry up to 3 times; then use cached last response if available; else escalate to human |
| Tool API down | Mark tool as unhealthy, skip, continue with partial evidence, flag in output |
| Human approver unreachable | Timeout after 15 min, escalate to backup on‑call; if no response in 30 min, auto‑reject with alert |
| State corruption | Use Postgres checkpoint with write‑ahead log; on resume, verify hash of state; if corrupted, reload from previous checkpoint and replay deterministic steps |
| Infinite agent loops | Recursion counter; after 2 consecutive calls of same agent, break and route to human |
| Invalid LLM output format (JSON parse failure) | Pydantic validation; on failure, retry with stricter prompt and error feedback; eventually fallback to a template‑based output |

---

## 16. Advanced Features (Stretch)

- **Agent Debate Protocol**: Multiple Root Cause sub‑agents argue alternative hypotheses, improving accuracy.
- **Self‑Evaluating Agent**: A meta‑agent that reviews the entire workflow and flags procedural errors.
- **Cost‑Aware Router**: Shunts simple classifications to a smaller, cheaper model.
- **Adaptive Workflow**: The graph dynamically expands if early evidence is contradictory.
- **Anomaly Dashboard Integration**: Pulls in real‑time prediction anomalies from an external service.
- **Federated Learning for Pattern Improvement**: Anonymised incident patterns pooled across installations (with consent) to improve the pattern library.

---

## 17. Project Delivery & Curriculum Alignment

| Phase | Key Educational Goal | Resulting Deliverable |
|-------|----------------------|----------------------|
| 1-2 | Agents vs. workflows, prompt design, tool use | Single‑agent classifier with Prometheus tool, evaluation of classification |
| 3-5 | Workflows (n8n vs code), retrieval pragmatism | Low‑code triage prototype, then Python agent with tool loop and RAG over runbook |
| 6-7 | State, memory, evaluation | Session state support, eval harness with 20 incidents for classification |
| 8 | Guardrails & human‑in‑loop | LangGraph interrupt node for approval, risk gate logic |
| 9-10 | Multi‑agent decomposition, LangGraph | Full graph with router, metrics, logs, deployment agents; checkpointing |
| 11-13 | External APIs, tool integration, core build | Connect to Loki, GitHub; deploy root cause agent with evidence grounding; build risk and postmortem agents as described |
| 14-15 | Evaluation, reliability, shipping | Integrate full eval pipeline, polish UI, deploy on Render/Railway, create demo video |
| 16 | Presentation & review | Live drill, showcase evidence tracing, risk quantification, approval flow |

---

## 18. MVP Definition

**Must include**:
- Incident ingestion via webhook (mocked Prometheus payload)
- Router, Metrics, Logs, Deployment, Root Cause (with evidence grounding and temporal checks), Risk (with quantitative blast radius), Remediation, and Postmortem agents
- LangGraph orchestration with checkpointing, retries, and human interrupt on dangerous actions
- Approval UI
- Full evaluation framework with 30 synthetic scenarios
- Frontend dashboard showing incident timeline and agent trace
- Postmortem generation to template with contributing factor analysis

**MVP success**: The system can autonomously process a synthetic “database latency” incident from alert to postmortem, correctly identify a deployment as root cause, quantify risk, pause for approval on a database restart, and generate a 5‑Whys postmortem with actionable items — all while logging every step for evaluation.

---

## 19. Closing Note

SentinelOps AI is deliberately designed to be a reference architecture for serious AI systems. It eschews the “chat‑with‑your‑data” paradigm in favor of structured, evidence‑based reasoning, durable orchestration, and rigorous evaluation. The detailed design of the Root Cause, Risk, and Postmortem agents transforms them from superficial summarizers into deep, trustworthy components that embody real SRE principles. This platform demonstrates that AI agents, when properly constrained and grounded, can dramatically improve incident response without sacrificing reliability or control.