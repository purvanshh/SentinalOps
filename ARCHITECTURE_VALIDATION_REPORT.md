# Architecture Validation Report

**Date:** 2026-05-16
**Validator:** DependencyGraphValidator + LayerBoundaryValidator + ObservabilityCoverageAuditor

---

## Layer Architecture

SentinelOps follows a layered architecture with explicit dependency directions:

```
api
 └─► orchestration ──► agents ──► core
      └─► evaluation ──► core, replay
 └─► runtime ──► core, orchestration, evaluation

observability ──► core
validation ──► core
operators ──► core, evaluation
ingestion ──► core
causality ──► core
semantics ──► core
```

Dependency direction: source layer may import from listed target layers only.
Reverse imports violate layer boundaries.

---

## Known Architectural Violations

### eval → runtime coupling (pre-existing, Phase 48)

**File:** `evaluation/replay_integration.py`
**Imports:** `runtime.continuous_evaluator`, `runtime.drift_monitor`, `runtime.operational_regression`

**Root cause:** Phase 48 integrated operational chaos evaluation directly into the
runtime continuous evaluation loop. The coupling was functional but violates
the intended layer boundary.

**Risk:** Changes to `runtime/` modules can break evaluation pipelines silently.

**Resolution:** Refactor `replay_integration.py` to use an interface or event
bus rather than direct imports from `runtime/`. Not resolved in Phase 50 to
avoid scope creep — documented here for future remediation.

---

## Observability Coverage

The ObservabilityCoverageAuditor checked all non-test source modules.

A module is considered instrumented if it contains any of:
`logger`, `logging`, `metrics`, `prometheus`, `trace`, `span`, `structlog`, `sentry`

**Coverage target: ≥80%** (audit-grade threshold)

Modules without any instrumentation are production blind spots — failures
in those modules produce no observable signal.

---

## Cycle Detection

No cycles were detected in the module import graph that involve the Phase 50
new modules. The DependencyGraphValidator scans all `.py` files under `src/`
using AST-level import extraction.

---

## Orphan Modules

Orphan detection flags modules that are never imported by any other module.
Orphans may indicate:
- Unused utility code that should be removed
- Entry points or CLI scripts (expected to be orphans)
- Modules that exist in the wrong location

The validator reports orphans for manual review — it does not automatically
classify them as problems.

---

## What Was Not Checked

- Runtime type safety (mypy was not configured project-wide)
- Global state mutations (no AST analysis of global variable assignments)
- Thread safety (no concurrency analysis)
- Memory leaks (no profiling)

These are out of scope for static analysis and require dynamic instrumentation.
