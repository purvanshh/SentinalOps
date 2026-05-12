# Orchestration Stability Report

## VERIFIED

- Worker crash recovery now completes through replay instead of hanging indefinitely.
  - Live incident: `3a5f8fd6-82b1-4e92-b09e-004fdf037713`
  - Evidence: task replayed after stale-heartbeat detection, `replay_count=1`, final status `resolved_degraded`.
- Redis outage during enqueue no longer drops the incident.
  - Live incident: `9f39e153-403c-4acf-bdf3-c60259b7dde5`
  - Evidence: webhook returned `201`, pending task retained the broker DNS failure, replay later completed with `replay_count=1`.
- Concurrent incidents remain isolated by `thread_id`.
  - Live incidents:
    - `ce514da4-723a-4446-86c0-0042c3f0ed0e`
    - `fd092a48-4163-4ee1-aeeb-5d3496304eb8`
    - `6688aae1-cb81-4dcb-a02d-1ddb28e95e3b`
  - Evidence: distinct `thread_id`, distinct execution lineage, no shared checkpoint state.
- Corrupt latest checkpoints are detected and skipped.
  - Live thread: `afa81018-e60d-418d-9e3a-086ad1d3ee9a`
  - Evidence: `checkpoint_corruption_detected` logged twice and API returned the previous valid checkpoint (`postmortem_report`) instead of the corrupted `completed` row.

## PARTIALLY VERIFIED

- Approval pause and resume are durable across worker restart.
  - Live incident: `dcfa0058-9c81-4207-9b9b-3e6d8e0d44a1`
  - Verified: approval row survived worker restart and resume completed through the API.
  - Not fully verified: this path was seeded directly into the live graph state to hit the interrupt deterministically because the current provider posture keeps natural incidents in `SAFE_MODE`.
- Cross-process LangGraph resume is operating through persisted state fallback, not through a durable LangGraph checkpointer.
  - The runtime still logs `langgraph_checkpointer_fallback backend=MemorySaver`.

## ASSUMED

- Recovery behavior under multi-worker horizontal scaling beyond the single local worker container.
- Replay behavior under Redis eviction pressure rather than explicit outage/restart.

## FAILED

- None in the final Phase 37 validation set after the runtime fixes.

## Key Tradeoffs

- The orchestration layer now prefers replayability over immediate fail-fast semantics.
- We intentionally rebuild graph-scoped async state per worker execution to avoid loop contamination; this reduces elegance but improves retry safety.
- Replay now triggers sooner (`20s` stale threshold, `10s` sweep), which improves crash recovery but increases sensitivity to genuinely long-running stuck tasks.
