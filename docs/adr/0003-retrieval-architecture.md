# ADR 0003: Retrieval Architecture

## Status

Accepted

## Context

SentinelOps needs retrieval for static knowledge domains without leaking live telemetry into vector search. Patterns, past incidents, runbooks, and prevention items all need different lifecycles but should share a common indexing and search layer.

## Decision

Use Qdrant as the common vector backend with a retrieval orchestrator that owns:

- collection bootstrap
- indexing helpers
- fallback-safe search behavior
- separation between pattern, incident, runbook, and prevention collections

## Consequences

- Retrieval can fail open without collapsing the incident workflow.
- Indexing logic stays centralized instead of being scattered across agents.
- The platform can gradually replace stub embeddings with stronger embedding providers later.
