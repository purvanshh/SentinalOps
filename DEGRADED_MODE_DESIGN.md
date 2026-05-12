# Degraded Mode Design

## Operating Modes

### `FULL`
- Providers are available.
- LLM calls are allowed.
- Automated actions are allowed, subject to existing approval gates.

### `DEGRADED`
- Primary provider is exhausted or circuit-open.
- Workflow is still active.
- System attempts alternate providers.

### `SAFE_MODE`
- All live provider layers are exhausted.
- Deterministic fallback is active.
- LLM calls are disabled.
- Automated execution is disabled.
- Workflow continues as observation and decision-support only.

## VERIFIED
- `FULL -> DEGRADED -> SAFE_MODE` transitions were observed in live worker logs.
- Mode transitions are persisted into graph/runtime state and surfaced by the incident APIs.
- `SAFE_MODE` prevents autonomous execution and approval-triggered execution paths.

## PARTIALLY VERIFIED
- `LOCAL_ONLY` and `OBSERVE_ONLY` exist conceptually in the phase requirements, but the live runtime exercised `FULL`, `DEGRADED`, and `SAFE_MODE`.

## ASSUMED
- A configured, healthy local model would allow a meaningful `LOCAL_ONLY` steady state.

## FAILED
- None for the specific modes exercised in live validation.

## Mode Transition Evidence
- Repeated 429:
  - `FULL -> DEGRADED` after primary provider exhaustion
  - `DEGRADED -> SAFE_MODE` after local provider failure
- Timeout:
  - same transition sequence after primary timeouts and local provider failure

## Design Intent
- Never let the workflow disappear because the model layer is unavailable.
- Continue classification and downstream orchestration with deterministic outputs where needed.
- Preserve operator visibility even when decision quality is degraded.
