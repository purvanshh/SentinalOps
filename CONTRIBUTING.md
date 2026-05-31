# Contributing to SentinelOps

Thank you for helping build the future of autonomous incident response.

## Development Guidelines
1. We follow Trunk-Based Development. All feature branches (`feat/`, `fix/`, `docs/`) must merge to `main` via PRs.
2. Direct commits to `main` are restricted.
3. Every pull request must pass the CI gate, including all unit and integration tests.

## Development Workflow
```bash
cp .env.example .env
make up
.venv/bin/pytest
```
