# SentinelOps AI

SentinelOps AI is an autonomous multi-agent incident investigation and reliability orchestration platform.

## Current Status

This repository currently includes:

- Phase 1 foundation: monorepo scaffold, FastAPI backend skeleton, Docker Compose stack, observability stubs, and worker bootstrap
- Phase 2 intake layer: incident database models, repositories, webhook ingestion, and initial background pipeline task

## Quick Start

1. Copy `.env.example` to `.env`.
2. Run `make up`.
3. Open `http://localhost:8000/docs` or `http://localhost:8000/health`.
