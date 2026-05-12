# Checkpoint Integrity Report

## VERIFIED

- Corrupted latest checkpoint rows are skipped in favor of the latest valid checkpoint.
  - Corrupted thread: `afa81018-e60d-418d-9e3a-086ad1d3ee9a`
  - Manually corrupted row: `node_name=completed`
  - Recovery result: API returned the prior valid `postmortem_report` checkpoint.
- Corruption is operator-visible in logs.
  - Observed event: `checkpoint_corruption_detected`

## PARTIALLY VERIFIED

- Recovery uses the repository-backed checkpoint store successfully, but LangGraph itself is still backed by `MemorySaver` in this runtime.
  - Durable cross-process recovery is therefore implemented by SentinelOps’ own persisted state and checkpoint records, not by LangGraph’s native durable checkpointer.

## ASSUMED

- Recovery from multiple consecutive corrupt checkpoint rows would continue scanning until a valid row is found.

## FAILED

- None in the final checkpoint corruption drill.

## Known Gaps

- The running images do not include `langgraph-checkpoint-postgres`.
- Redis state can still be newer than PostgreSQL if a crash happens between the two writes; the system is now resilient to a bad latest checkpoint, but not fully transactional across both stores.
