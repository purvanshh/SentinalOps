# Queue Resilience Analysis

## VERIFIED

- Broker outage during enqueue does not drop the incident.
  - Live incident: `9f39e153-403c-4acf-bdf3-c60259b7dde5`
  - API still returned `201 Created`.
  - Deferred task state preserved the broker failure reason.
- Replay sweeper now recovers stale `running` and stale `replaying` tasks.
- Replay budgets are enforced in code and dead-letter promotion remains visible through persisted task status.

## PARTIALLY VERIFIED

- Dead-letter visibility is code-complete and unit-tested, but the live Phase 37 run did not intentionally exhaust replay attempts to force a dead-letter row.
- Celery result-backend reconnect failure is visible in the API logs during Redis outage, but the local validation did not require a full API restart to continue once Redis returned.

## ASSUMED

- Poison messages that repeatedly fail in the same deterministic way will eventually move to `dead_letter` under repeated replay cycles.

## FAILED

- None in the final enqueue/replay validation path.

## Live Evidence

- During Redis outage, API logs showed repeated result-backend reconnect failures.
- After Redis returned, the replay worker re-dispatched the deferred task and the incident completed with:
  - `status=resolved_degraded`
  - `replay_count=1`
  - preserved `last_error=Error -2 connecting to redis:6379. Name or service not known.`
