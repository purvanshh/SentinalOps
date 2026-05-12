# Provider Failover Trace

## Scenario A: Repeated 429

### VERIFIED
- Incident: `94474b71-87cc-4114-98bf-538101889bba`
- Primary provider returned `429 Too Many Requests` repeatedly.
- Local provider returned `ConnectError: All connection attempts failed`.
- Deterministic fallback classifier activated.
- Final state:
  - `operating_mode = SAFE_MODE`
  - `graph_status = completed_degraded`
  - `last_successful_step = postmortem_report`

### Key Trace Facts
- Primary retry count: `3`
- Local retry count: `2`
- Fallback layer used: `4`
- Total fallback-chain latency: about `5.6s`

## Scenario B: Provider Timeout

### VERIFIED
- Incident: `3586a6aa-3219-4234-beaa-8f47bf027833`
- Primary provider hit repeated `ConnectTimeout`.
- Local provider returned `ConnectError`.
- Deterministic fallback classifier activated.
- Final incident API state showed:
  - `operating_mode = SAFE_MODE`
  - `graph_status = completed_degraded`
  - `fallback_activated = true`

### Key Trace Facts
- Primary timeout retry count: `3`
- Local retry count: `2`
- Fallback layer used: `4`
- Router fallback latency: about `93.6s`

## Scenario C: Worker Restart

### VERIFIED
- Incident: `8ee41da5-e806-4b37-aba9-86271fa0bd9a`
- Worker was restarted during processing.
- Workflow eventually resumed and completed in degraded mode.
- Persisted task state in Postgres showed recovery and completion.

## PARTIALLY VERIFIED
- A true secondary remote provider was not exercised live because it was not configured.
- The final replay-threshold guardrail (`300s`) was restored after the timeout validation, but that exact number was not rerun through another full timeout incident.

## FAILED
- None for the exercised fallback chain itself.

## Notable Runtime Caveats
- LangGraph Postgres checkpointer was unavailable, so cross-process checkpointing used `MemorySaver`.
- API/trace visibility still remained available through Redis-backed runtime state.
