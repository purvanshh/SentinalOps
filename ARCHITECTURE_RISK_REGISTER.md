# Architecture Risk Register

Date: 2026-05-11

## R1. Single-provider dependency at first workflow step

Status: VERIFIED
Severity: Critical

Description:

The router classification step depends directly on a live external provider. When that provider returns `429`, the entire incident lifecycle stops before any meaningful graph progression.

Likely failure mode:

- incident ingestion succeeds
- queue consumption succeeds
- classification fails
- no incident response output is produced

Mitigation:

- deterministic fallback classifier
- alternate provider or model fallback
- circuit breaker and quota-aware admission control

## R2. No persisted early workflow envelope

Status: VERIFIED
Severity: High

Description:

The incident row exists, but no `graph_thread_id` or agent execution trace is persisted before the first LLM step.

Operational risk:

- operator sees an open incident with no explanation
- poor recoverability
- unclear replay semantics

Mitigation:

- persist bootstrap checkpoint before classification

## R3. Celery async boundary fragility

Status: VERIFIED
Severity: High

Description:

The worker path showed an intermediate retry caused by `RuntimeError('Event loop is closed')`.

Operational risk:

- nondeterministic worker behavior under retries
- possible resource leakage under load

Mitigation:

- replace `asyncio.run(...)` task boundary with a safer worker execution pattern

## R4. Excessive infrastructure before critical-path resilience

Status: VERIFIED
Severity: Medium

Description:

The system carries Grafana, Tempo, Loki, Qdrant, LangGraph, Celery, Redis, Postgres, and a dashboard, but the first agent call is not resilient.

Overengineering signal:

- operational surface area is large relative to validated business value

Mitigation:

- prioritize critical-path resilience before adding more platform complexity

## R5. Qdrant hot-path collection management

Status: VERIFIED
Severity: Medium

Description:

The worker touches collection creation/check existence during live incident handling.

Operational risk:

- unnecessary latency
- noisy logs
- hidden coordination issues under scale

Mitigation:

- move collection bootstrap to startup/migration path

## R6. Dashboard correctness not proven

Status: PARTIALLY VERIFIED
Severity: Medium

Description:

The dashboard HTTP surface is reachable, but no successful operator flow was validated against a completed incident lifecycle.

Mitigation:

- browser-level validation against a completed incident run

## R7. Observability completeness depends on success path

Status: PARTIALLY VERIFIED
Severity: Medium

Description:

Platform observability endpoints are reachable, but the team has not validated a full successful trace from ingest to postmortem.

Mitigation:

- add release smoke test that asserts a complete trace exists after a synthetic incident

## R8. Production auth assumptions still lightly proven

Status: PARTIALLY VERIFIED
Severity: Medium

Description:

Local JWT validation works, but Auth0-like production behavior was not validated against JWKS or real external issuer flows.

Mitigation:

- production-mode auth integration test

## R9. Approval and remediation layers remain unproven

Status: FAILED
Severity: High

Description:

Because the lifecycle never passed router classification, approval and execution safety paths remain architecturally present but operationally unproven.

Mitigation:

- complete a live safe-action incident through approval and execution

## R10. Likely production failure modes

Status: VERIFIED
Severity: Critical

Likely modes:

- provider quota exhaustion blocks all incidents
- queue retries amplify provider pressure
- operator sees incidents stuck open with no actionable trace
- traces/metrics appear healthy while product behavior is failing
