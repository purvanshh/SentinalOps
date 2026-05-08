# SentinelOps AI

SentinelOps AI is an autonomous multi-agent incident investigation and reliability orchestration platform.

## Current Status

This repository currently includes:

- Phase 1 foundation: monorepo scaffold, FastAPI backend skeleton, Docker Compose stack, observability stubs, and worker bootstrap
- Phase 2 intake layer: incident database models, repositories, webhook ingestion, and initial background pipeline task
- Phase 3 agent foundation: OpenAI-compatible LLM client, tool registry, and reusable multi-step agent loop
- Phase 4 router layer: incident classification agent with initial incident-history retrieval support
- Phase 5 observability evidence gathering: Prometheus and Loki tool wrappers plus Metrics and Logs agents
- Phase 6 deployment analysis: topology-aware GitHub deployment tooling and Deployment agent
- Phase 7 evidence-grounded root cause analysis: evidence normalization, pattern matching, causal validation, confidence scoring, and Root Cause agent integration
- Phase 8 quantitative risk assessment: blast-radius estimation, remediation risk scoring, historical action priors, and Risk agent integration
- Phase 9 approval workflow: remediation planning, pending approval state, approval APIs, Slack notification stubs, and timeout escalation scaffolding

## Quick Start

1. Copy `.env.example` to `.env`.
2. Run `make up`.
3. Open `http://localhost:8000/docs` or `http://localhost:8000/health`.
