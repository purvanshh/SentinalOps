# Resilience Implementation Report

## Scope
- Phase 36 / Critical Path Resilience
- Goal: keep the incident workflow alive when provider calls fail

## VERIFIED
- Deterministic fallback classification is implemented and used as layer 4 after provider exhaustion.
- Provider failover chain is implemented in this order:
  - primary provider
  - local OpenAI-compatible provider
  - deterministic fallback classifier
- Degraded operating modes are persisted and exposed:
  - `FULL`
  - `DEGRADED`
  - `SAFE_MODE`
- Bootstrap state is persisted before the first LLM call.
- Live 429 scenario completed successfully in degraded mode.
  - Incident: `94474b71-87cc-4114-98bf-538101889bba`
  - Incident: `89c69c84-140f-47c9-a407-951ee81046f1`
- Live timeout scenario completed successfully in degraded mode.
  - Incident: `3586a6aa-3219-4234-beaa-8f47bf027833`
- Worker restart scenario recovered and completed in degraded mode.
  - Incident: `8ee41da5-e806-4b37-aba9-86271fa0bd9a`
- Failure transparency is visible in API/trace payloads:
  - provider attempts
  - retry counts
  - fallback activation
  - operating mode transitions
  - provider health snapshots

## PARTIALLY VERIFIED
- Timeout-path replay protection was improved twice during validation.
  - Root cause: long provider timeout windows made the replay worker misclassify a still-running task as stale.
  - Final code now uses a much more conservative stale threshold.
  - The final `300s` threshold was restored into the codebase, but that exact guardrail was not rerun through a full timeout incident after the last rebuild.
- Cross-process graph checkpoint durability is not using Postgres in the live stack.
  - Runtime fell back to LangGraph `MemorySaver`.
  - Redis/API persistence still preserved operator visibility and degraded completion state.

## ASSUMED
- A true secondary remote provider layer is not actively configured in the current `.env`, so the live chain exercised:
  - primary remote provider
  - local provider
  - deterministic fallback
- Secondary-provider behavior is assumed from code paths, not from a live successful provider-2 run.

## FAILED
- Durable LangGraph checkpointing to Postgres was not active in the validated runtime.
- The production postmortem template path was missing in-container, so degraded postmortems were generated instead of the full template-backed document.

## Files Most Directly Changed
- `/Users/purvansh/Desktop/Projects/SentinalOps/apps/api-server/src/core/resilience/fallback_classifier.py`
- `/Users/purvansh/Desktop/Projects/SentinalOps/apps/api-server/src/core/resilience/provider_chain.py`
- `/Users/purvansh/Desktop/Projects/SentinalOps/apps/api-server/src/core/resilience/resilient_llm_client.py`
- `/Users/purvansh/Desktop/Projects/SentinalOps/apps/api-server/src/core/resilience/operating_mode.py`
- `/Users/purvansh/Desktop/Projects/SentinalOps/apps/api-server/src/core/resilience/node_fallbacks.py`
- `/Users/purvansh/Desktop/Projects/SentinalOps/apps/api-server/src/orchestration/graphs/main_graph.py`
- `/Users/purvansh/Desktop/Projects/SentinalOps/apps/api-server/src/orchestration/nodes/router_node.py`
- `/Users/purvansh/Desktop/Projects/SentinalOps/apps/api-server/src/orchestration/nodes/metrics_node.py`
- `/Users/purvansh/Desktop/Projects/SentinalOps/apps/api-server/src/orchestration/nodes/logs_node.py`
- `/Users/purvansh/Desktop/Projects/SentinalOps/apps/api-server/src/orchestration/nodes/deployment_node.py`
- `/Users/purvansh/Desktop/Projects/SentinalOps/apps/api-server/src/orchestration/nodes/approval_node.py`
- `/Users/purvansh/Desktop/Projects/SentinalOps/apps/api-server/src/orchestration/nodes/execution_node.py`
- `/Users/purvansh/Desktop/Projects/SentinalOps/apps/api-server/src/orchestration/nodes/postmortem_node.py`
- `/Users/purvansh/Desktop/Projects/SentinalOps/apps/api-server/src/workers/tasks/incident_pipeline.py`
- `/Users/purvansh/Desktop/Projects/SentinalOps/apps/api-server/src/api/routes/incidents.py`
- `/Users/purvansh/Desktop/Projects/SentinalOps/apps/api-server/src/api/routes/graph.py`

## Tradeoffs
- Reliability was favored over precision.
- `SAFE_MODE` disables autonomous execution after provider exhaustion.
- The replay threshold is intentionally conservative to avoid duplicate timeout-path execution.
