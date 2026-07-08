# SentinelOps

[![codecov](https://codecov.io/gh/purvanshh/SentinalOps/branch/main/graph/badge.svg)](https://codecov.io/gh/purvanshh/SentinalOps)
[![CI Status](https://github.com/purvanshh/SentinalOps/actions/workflows/ci.yml/badge.svg)](https://github.com/purvanshh/SentinalOps/actions/workflows/ci.yml)

**Autonomous Multi-Agent Incident Response and Reliability Orchestration Platform**

> **Current Limitations:** SentinelOps is currently a development prototype. Leading metric Root Cause Match is at **11.93% (lexical) / 14.68% (semantic)** accuracy under simulation. Autonomy is disabled; human supervision is required for all actions.

## Quickstart

```bash
cp .env.example .env
make up
curl http://localhost:8000/health
.venv/bin/pytest
```

## System Architecture

SentinelOps uses a cooperative multi-agent architecture powered by LangGraph. Details are documented in [docs/architecture/current.md](docs/architecture/current.md).

## Project Status

| Metric | Target | Current Value | Status |
| :--- | :--- | :--- | :--- |
| Root Cause Match (top-1) | >75% | **11.93% (lexical) / 14.68% (semantic)** | Warning |
| Classification Accuracy | >90% | **99.17%** | Passing |
| Evidence Grounding Score | >0.95 | **98.4%** | Passing |

See [docs/getting-started.md](docs/getting-started.md) for full onboarding.
