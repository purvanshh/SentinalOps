# On-Call Guide

## Typical demo flow

1. Trigger an incident through `POST /incidents/webhook`.
2. Start the graph or allow the worker pipeline to invoke it.
3. Review the approval queue when remediation pauses.
4. Resume with approval.
5. Inspect the generated postmortem and evaluation summary.

## Failure triage

- If approvals are stuck, inspect the in-memory approval queue and graph checkpoint rows.
- If graph execution stalls, inspect `workflow_checkpoints` and recent `agent_executions`.
- If evaluation output looks stale, rerun the evaluation route or CI workflow.
