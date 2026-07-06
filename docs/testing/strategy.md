# Test Strategy and Test Pyramid Rationalization

SentinelOps rationalizes its test strategy into a coherent 4-layer pyramid.

## 1. Unit Tests (`unit/`)
- **Objective:** Verify pure functions, core class logic, and algorithms in complete isolation.
- **Constraints:** Must run without any network or file system dependencies. Total suite execution must be < 30 seconds.
- **Run:** `pytest -m unit`

## 2. Integration Tests (`integration/`)
- **Objective:** Verify database operations, repository classes, messaging layers, and API endpoint contracts against real Docker-backed infrastructure.
- **Run:** `pytest -m integration`

## 3. End-to-End Tests (`e2e/`)
- **Objective:** Verify full transaction flows (alert ingestion -> graph routing -> mitigation execution -> human approval -> postmortem generation).
- **Run:** `pytest -m e2e`

## 4. Evaluation Tests (`evaluation/`)
- **Objective:** Verify agent accuracy, retrieval precision/recall, red-team resilience, and model-level regressions.
- **Run:** `pytest -m evaluation`
