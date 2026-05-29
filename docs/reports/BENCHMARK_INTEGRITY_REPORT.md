# Benchmark Integrity Report

**Date:** 2026-05-16
**Framework version:** Phase 50

---

## Purpose

This report documents the anti-contamination and integrity measures applied
to all SentinelOps benchmark evaluations. Its purpose is to support external
verification that benchmark scores are not inflated by:
- golden label leakage into scorer inputs
- evaluation-time data cleaning not applied in production
- hidden benchmark assumptions
- evaluation-only logic paths

---

## Anti-Contamination Measures

### Contamination Field Patterns (blocked from scorer input)

The `AntiContaminationGuard` blocks these field patterns from reaching any scorer:

- `golden_label`, `true_label`, `ground_truth`
- `root_cause` (causal ground truth — must not be prediction input)
- `_label`, `correct_answer`, `expected_output`
- `_golden`, `_contamination`

Any evaluation pipeline must call `AntiContaminationGuard.assert_clean()`
before invoking a scorer. This is a hard gate — contamination raises `ContaminationError`.

### Contamination Detection Results

The operational chaos dataset (`simulation/datasets/operational_chaos/incidents.json`)
was checked at Phase 50 integration:
- **Result: 0 contaminated samples out of 40**
- No golden label fields present in scorer-visible input fields

---

## Invariant Verification

The `BenchmarkInvariantChecker` verifies 5 cross-cutting invariants on every evaluation run:

| Invariant | Status |
|---|---|
| Scorer never receives golden label fields | ENFORCED |
| Confidence values remain in [0.0, 1.0] | ENFORCED |
| Attribution requires minimum 0.20 confidence | ENFORCED |
| Evaluation uses actual runtime outputs, not mocks | ENFORCED |
| No evaluation-only code paths active | ENFORCED |

---

## Evaluation Path Audit

The `EvaluationPathAuditor` verified:
- Production and evaluation pipelines use identical confidence calibration
- Evaluation does not apply extra data cleaning
- Evaluation does not use data unavailable at inference time
- Evaluation does not disable uncertainty checks

**Synthetic inflation risk: NONE** (for the standard benchmark pipeline)

---

## Reproducibility Guarantees

| Guarantee | Method |
|---|---|
| Dataset mutation detection | SHA-256 fingerprint of all serialized items |
| Environment drift detection | Package version snapshot comparison |
| Hidden randomness detection | Seed enforcement + output checksum comparison |
| Benchmark drift detection | Metric-level consistency checking with tolerance |
| Run provenance | ReplayManifest with run ID, timestamp, checksum |

---

## Benchmark Weaknesses

1. **Dataset is synthetic**: Scores apply only to the simulated incident distribution.
   Real-world incidents may have different statistical properties.

2. **LLM non-determinism**: Reasoning outputs vary across runs even with fixed seeds.
   Only the evaluation scaffolding (not LLM outputs) is fully reproducible.

3. **Single evaluator**: Benchmark metrics were developed by the same team that
   built the system. External independent evaluation has not been performed.

4. **Limited dataset size**: The operational chaos dataset contains 40 incidents.
   Confidence intervals on all metrics are wide. Point estimates should not be
   treated as reliable population statistics.

5. **Label construction**: Root-cause labels in the chaos dataset were assigned by
   the simulation generator, not by human incident responders.

---

## Conclusion

The benchmark pipeline is protected against common sources of contamination
and evaluation-time shortcuts. All reported metrics reflect actual runtime
outputs on labeled synthetic incidents.

The fundamental limitation — synthetic data — cannot be resolved within this
framework. Any production adoption decision must include shadow-mode evaluation
on real incident telemetry.
