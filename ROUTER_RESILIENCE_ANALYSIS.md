# Router Resilience Analysis

## VERIFIED
- Router bootstrap state is persisted before the first provider call.
- Primary-provider retries are bounded.
- Primary-provider failures open a circuit breaker.
- Local-provider failures trigger deterministic fallback.
- Router outputs include:
  - retry history
  - provider attempts
  - provider health snapshot
  - fallback layer used
  - operating mode

## PARTIALLY VERIFIED
- Router timeout handling is live-proven, but long timeout budgets interact with task replay policy.
- The final stale-task threshold hardening is in code and restored into the runtime baseline, but that exact value was not rerun through another full timeout incident after the final rebuild.

## ASSUMED
- If a secondary remote provider is configured later, the same resilience envelope should apply to layer 2.

## FAILED
- Router durability still depends on Redis/API state exposure plus DB logs rather than a live Postgres LangGraph checkpointer.

## Main Failure Modes Observed

### Rate limit exhaustion
- Primary provider emitted repeated `429`.
- Circuit opened after bounded retries.
- Workflow continued in `SAFE_MODE`.

### Timeout exhaustion
- Primary provider emitted repeated `ConnectTimeout`.
- Long timeout budgets exposed replay-staleness sensitivity.
- Workflow still completed, but the replay window required hardening.

### Local model unavailability
- Local provider emitted `ConnectError`.
- Deterministic fallback activated consistently.

## Risks Introduced by the Hardening
- Conservative replay thresholds improve safety but may delay restart recovery for genuinely dead workers.
- `SAFE_MODE` preserves continuity but reduces action quality and disables automation.
- Because the router persists degraded outputs, downstream agents can proceed on limited evidence; that is intentional, but the outputs are only decision-support quality.
