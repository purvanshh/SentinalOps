# ADR 0001: Workflow Graph as Orchestration Backbone

## Status
Accepted

## Context
SentinelOps needs resumable, inspectable incident execution with interrupt points for approvals.

## Decision
Use a checkpoint-backed workflow graph abstraction with node-level persistence and explicit start/resume APIs.

## Consequences
- Easier incident traceability
- Natural place for human interrupts
- More structured than a linear background task pipeline
