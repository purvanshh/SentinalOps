# REGRESSION EVALUATION FRAMEWORK — Phase 39

## Purpose

The regression evaluation framework provides automated detection of AI decision
quality regressions across benchmark versions, model updates, and prompt changes.

A regression is defined as a meaningful degradation in any tracked metric beyond
an acceptable threshold between two evaluation runs.

## Architecture

```
BenchmarkSuite (benchmark_suite_v1.json)
        │
        ▼
  replay_benchmark()
        │
        ├── score_router_quality()
        ├── score_confidence_calibration()
        ├── score_remediation_quality()
        ├── score_execution_safety()
        ├── score_operator_trust()
        └── score_hallucination_from_benchmark()
        │
        ▼
  ReplayResult (timestamped, hashed)
        │
        ▼
  compare_runs(baseline, current)
        │
        ▼
  RegressionReport
```

## Reproducibility Guarantees

**Status: VERIFIED**

The benchmark replay is fully deterministic:

1. **Stable input**: `benchmark_suite_v1.json` is immutable
2. **Stable hash**: `replay_hash = ddf715d1d54bba67` is always the same for v1 suite
3. **Deterministic scores**: identical scores on every replay of the same suite
4. **Version tracking**: suite version embedded in every ReplayResult

Verified by test: `test_replay_is_deterministic` runs replay twice and asserts
identical hash and scores.

## Tracked Metrics

| Metric | Source | Regression Threshold | Direction |
|--------|--------|---------------------|-----------|
| `accuracy` | Router quality | 2% drop | Higher is better |
| `macro_f1` | Router quality | 2% drop | Higher is better |
| `macro_precision` | Router quality | 2% drop | Higher is better |
| `macro_recall` | Router quality | 2% drop | Higher is better |
| `calibration_error` | Calibration | 3% increase | Lower is better |
| `brier_score` | Calibration | 3% increase | Lower is better |
| `hallucination_rate` | Hallucination | 5% increase | Lower is better |
| `safe_rate` | Remediation | 3% drop | Higher is better |
| `dangerous_rate` | Remediation | 2% increase | Lower is better |
| `mean_quality_score` | Remediation | 3% drop | Higher is better |
| `execution_safety` | Safety | 3% drop | Higher is better |
| `trust_score` | Operator trust | 3% drop | Higher is better |
| `dangerous_rejection_rate` | Operator trust | 2% drop | Higher is better |
| `trustworthiness` | Aggregate | 3% drop | Higher is better |
| `safety_score` | Aggregate | 3% drop | Higher is better |
| `autonomous_readiness` | Aggregate | 3% drop | Higher is better |

## Regression Severity

| Severity | Definition | Required Action |
|----------|-----------|-----------------|
| LOW | 1x–2x threshold exceeded | Log and monitor |
| MEDIUM | 2x–3x threshold exceeded | Alert engineering |
| HIGH | 3x+ threshold exceeded | Block release candidate |
| CRITICAL | Any metric drops to 0 or catastrophic values | Halt deployment |

## Baseline Results (Phase 39)

```
Suite: benchmark-v1 (ddf715d1d54bba67)
Date: 2026-05-13

accuracy:                  1.0000
macro_f1:                  1.0000
calibration_error:         0.2755
hallucination_rate:        0.1226
safe_rate:                 0.9057
dangerous_rate:            0.0755
mean_quality_score:        0.7670
execution_safety:          0.7094
trust_score:               0.8013
trustworthiness:           0.8139
safety_score:              0.8700
autonomous_readiness:      0.8901
```

**Status: VERIFIED — This is the reference baseline for all future comparisons.**

## Usage

### Running a Baseline Evaluation

```python
from evaluation.regression.benchmark_replay import replay_benchmark

baseline = replay_benchmark()
print(f"Baseline hash: {baseline.replay_hash}")
print(f"Trustworthiness: {baseline.aggregate_trustworthiness_score:.4f}")
```

### Detecting Regressions

```python
from evaluation.regression.regression_evaluator import detect_regressions

regressions = detect_regressions(baseline, current)
if regressions:
    for r in regressions:
        print(f"REGRESSION: {r.metric} dropped by {abs(r.delta):.4f} ({r.severity})")
```

### Full Comparison

```python
from evaluation.regression.regression_evaluator import compare_runs

report = compare_runs(baseline, current)
print(f"Regressions: {len(report.regressions)}")
print(f"Improvements: {len(report.improvements)}")
print(f"Has critical: {report.has_critical_regression}")
```

## CI Integration Requirements

**Status: ASSUMED — CI pipeline not yet configured**

The regression framework should be integrated into CI as follows:

1. **Store baseline**: After each approved major change, store the `ReplayResult`
   as a JSON artifact
2. **Run on PR**: Every pull request runs `replay_benchmark()` and calls
   `compare_runs(baseline, current)`
3. **Block on CRITICAL**: Any CRITICAL regression blocks the PR
4. **Alert on HIGH**: HIGH regressions send alerts to #engineering-alerts
5. **Annotate on MEDIUM**: MEDIUM regressions are annotated in the PR review

## Benchmark Versioning Policy

| Event | Required Action |
|-------|----------------|
| Model update | Run full regression comparison |
| Prompt change | Run full regression comparison |
| Provider fallback change | Run degraded-mode regression comparison |
| New incident categories | Update benchmark suite (new version) |
| Algorithm change in scorers | Re-verify baseline scores |

When upgrading from v1 to v2 benchmark suite:
1. Run v2 suite
2. Compare v2 vs. v2 (self) to establish new baseline
3. Document score changes between v1 and v2 baselines

## Test Coverage

| Test | What It Validates |
|------|-------------------|
| `test_replay_produces_result` | Replay completes without errors |
| `test_replay_is_deterministic` | Same hash and scores on two runs |
| `test_identical_runs_have_no_regressions` | Zero regressions when comparing run to itself |
| `test_degraded_accuracy_detected_as_regression` | Regression detection fires on accuracy drop |
| `test_improved_accuracy_detected_as_improvement` | Improvement detection fires on accuracy gain |
| `test_regression_severity_levels_valid` | Severity values are valid enum members |

**Status: VERIFIED — 22 tests, all passing**
