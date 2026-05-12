# Worker Failure Analysis

## VERIFIED

- A hard `SIGKILL` against `celery-worker` no longer causes silent incident loss.
  - Drill incident: `3a5f8fd6-82b1-4e92-b09e-004fdf037713`
  - Before fix: task stuck at `bootstrapped`/`classified` with no replay.
  - After fix: stale-running task replayed, execution lineage captured both worker runs, incident resolved in degraded mode.
- Replay lineage is now operator-visible in `/graph/incidents/{id}/trace`.
  - Evidence fields: `execution_lineage`, `replay_count`, `last_replay_reason`, `lease_owner`, `last_heartbeat_at`.

## PARTIALLY VERIFIED

- Celery retry corruption from stale graph-bound async clients appears mitigated by resetting the graph singleton per worker execution.
  - Verified in the crash/replay drill.
  - Not yet validated under prolonged repeated retries across many hours.

## ASSUMED

- OOM-style worker termination will behave equivalently to `SIGKILL` because the task uses `acks_late=True` and replay is driven from persisted task state.

## FAILED

- Initial Phase 37 worker crash drill failed before the fix.
  - Incident: `46527cbf-44d6-407e-afe0-c64f4713c93b`
  - Observed failure:
    - `RuntimeError('Event loop is closed')`
    - task wedged at `dispatch_evidence`
    - stale-running recovery too slow to be operationally useful
  - This failure is now the regression case the final implementation addresses.

## Root Causes Addressed

- Graph-scoped async state was being reused across worker attempts longer than it should.
- Replay relied on a stale threshold tuned for provider latency, not crash recovery.
- Replay selection ignored stale `replaying` tasks.

## Remaining Risks

- The worker still runs as root inside Docker.
- The API logs show Celery result-backend reconnect exhaustion during full Redis outage; recovery still succeeds, but the result backend is noisy and not restart-free.
