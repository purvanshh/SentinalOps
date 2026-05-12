# Concurrency Test Results

## VERIFIED

- Three live incidents executed concurrently without cross-incident contamination.
  - Incident `ce514da4-723a-4446-86c0-0042c3f0ed0e` -> thread `afa81018-e60d-418d-9e3a-086ad1d3ee9a`
  - Incident `fd092a48-4163-4ee1-aeeb-5d3496304eb8` -> thread `b215d2d5-8df7-48cb-8f10-11bac300891b`
  - Incident `6688aae1-cb81-4dcb-a02d-1ddb28e95e3b` -> thread `9cab9b3d-a87f-42ef-a2fc-06d46e8fca60`
- Each incident completed independently with:
  - `status=resolved_degraded`
  - `graph_status=completed_degraded`
  - `agent_count=7`
  - distinct execution lineage entries

## PARTIALLY VERIFIED

- Reducer correctness is indirectly supported by isolated `completed_nodes` and trace state, but there is no stress run yet with dozens of simultaneous incidents contending on the same broker.

## ASSUMED

- Database write contention remains acceptable above the three-incident local validation level.

## FAILED

- None in the validated local concurrency run.

## Observed Constraints

- All three incidents ran in `SAFE_MODE` because the primary provider returned `429` and the local provider was unavailable.
- This means concurrency isolation was proven on degraded orchestration, not on a fully LLM-backed path.
