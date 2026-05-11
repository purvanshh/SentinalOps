# On-Call Guide

## Typical operator flow

1. Trigger an incident through `POST /incidents/webhook`.
2. Start the graph or allow the worker pipeline to invoke it.
3. Watch progress from the dashboard or the incident WebSocket stream.
4. Review the approval queue when remediation pauses.
5. Resume with approval or reject with operator notes.
6. Inspect the generated postmortem and evaluation summary.

## Failure triage

- If approvals are stuck, inspect `approval_requests`, `workflow_checkpoints`, and recent Celery logs.
- If graph execution stalls, inspect `workflow_checkpoints` and recent `agent_executions`.
- If evaluation output looks stale, rerun the evaluation route or CI workflow.
- If retrieval hints disappear, verify Qdrant collection health and bootstrap status.
