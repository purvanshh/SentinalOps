# Execution Recovery Report

## VERIFIED

- Approval persistence survives a worker restart.
  - Seeded live incident: `dcfa0058-9c81-4207-9b9b-3e6d8e0d44a1`
  - Approval remained queryable through `/approvals` after worker restart.
- API resume now survives LangGraph version mismatch by falling back to persisted state recovery.
  - Fix: `langgraph.types.Command` import is now inside the guarded resume path.
  - Result: resume no longer returns `500` for this environment.

## PARTIALLY VERIFIED

- Approval interrupt and resume were validated using a seeded live graph state rather than a naturally reached approval gate.
  - Reason: the current provider environment naturally pushes incidents into `SAFE_MODE`, which disables autonomous execution and approval gates.
- The remediation action resumed and was marked `approved`, but the runtime tool execution still failed.
  - This proves pause/resume durability.
  - It does not prove successful autonomous remediation execution for this specific action.

## ASSUMED

- A naturally reached approval gate from a `FULL` mode incident will follow the same persisted-state resume behavior.

## FAILED

- Pre-fix resume path failed with:
  - `ImportError: cannot import name 'Command' from 'langgraph.types'`
  - This was a real live failure during the first approval validation attempt.

## Operational Notes

- The resumed incident completed with `status=resolved` but `graph_status=completed_degraded`.
- That mismatch should be treated as a semantic consistency issue for a later hardening phase, not a blocker to Phase 37’s durability goals.
