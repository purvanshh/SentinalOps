# Incident Survivability Report

## Objective
- Prove the incident lifecycle survives provider failures instead of dying silently.

## VERIFIED

### 1. 429-driven degraded completion
- Incident survived provider exhaustion.
- Classification still completed via deterministic fallback.
- Evidence gathering, root cause, risk, remediation planning, and degraded postmortem all completed.

### 2. Timeout-driven degraded completion
- Incident remained visible as `bootstrapped` during the long timeout budget.
- Router eventually degraded safely after timeout exhaustion.
- Downstream investigation still completed.

### 3. Worker restart survivability
- A worker interruption did not destroy the incident.
- Task persistence in Postgres allowed replay/recovery.
- Incident eventually completed in degraded mode.

## PARTIALLY VERIFIED
- Timeout-path duplicate replay was observed under shorter stale-task windows.
- The code now uses a more conservative stale threshold, but that exact final threshold was not revalidated with another full timeout run after the last restore-to-normal rebuild.

## ASSUMED
- Incidents with a healthy secondary provider would degrade less aggressively than the scenarios validated here.

## FAILED
- Full durable LangGraph resume semantics across process boundaries remain unavailable because the runtime is still using `MemorySaver`.

## Evidence by Incident

### `89c69c84-140f-47c9-a407-951ee81046f1`
- Final restored-stack 429 validation
- Final state:
  - `status = resolved_degraded`
  - `operating_mode = SAFE_MODE`
  - `graph_status = completed_degraded`

### `94474b71-87cc-4114-98bf-538101889bba`
- earlier 429 live validation
- degraded pipeline completed successfully

### `3586a6aa-3219-4234-beaa-8f47bf027833`
- timeout validation
- degraded pipeline completed successfully after provider timeouts
- replay race was discovered during this validation class and used to harden the stale-task guardrail

### `8ee41da5-e806-4b37-aba9-86271fa0bd9a`
- worker restart scenario
- degraded pipeline completed after recovery

## Main Survivability Conclusion
- The critical path no longer catastrophically fails at `incident -> provider failure -> dead workflow`.
- It now behaves as:
  - `incident -> provider failure -> degraded mode -> deterministic fallback -> continued workflow`
