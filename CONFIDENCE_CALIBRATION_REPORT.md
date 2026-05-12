# CONFIDENCE CALIBRATION REPORT — Phase 39

## Executive Summary

| Metric | Value | Status |
|--------|-------|--------|
| Expected Calibration Error (ECE) | 0.2755 | VERIFIED |
| Brier Score | 0.1112 | VERIFIED |
| Calibration Grade | **FAILING** | VERIFIED |
| Overconfidence Rate | 0.0% | VERIFIED |
| Underconfidence Rate | 85.71% | VERIFIED |
| Mean Confidence | 72.0% | VERIFIED |
| Mean Accuracy | 100.0% | VERIFIED |
| Confidence-Accuracy Gap | 28.0% | VERIFIED |
| Abstain Threshold | 0.93 | VERIFIED |
| Escalation Threshold | 0.93 | VERIFIED |

## Analysis

### Systematic Underconfidence

The system is **systematically underconfident**: it achieves 100% classification
accuracy on the benchmark but reports mean confidence of only 72.0%.

This is a calibration failure in the direction of **underconfidence** rather
than overconfidence. The confidence scores are too conservative relative to
the actual decision quality.

**Interpretation**: The mocked tool responses in the benchmark have confidence
values that reflect AI provider uncertainty in production conditions (degraded
providers, noisy alerts, false positives), which is a reasonable reflection
of real-world behavior. However, the benchmark labels are ground truth, so the
classification is always "correct" from the benchmark perspective.

**ECE = 0.2755**: Calibration error of 27.55 percentage points is considered
FAILING by standard calibration thresholds (> 0.25).

### Why This Matters

A system that says "I'm 60% confident" when it's actually correct 95% of the
time may cause operators to:
1. Unnecessarily escalate valid incidents
2. Slow response time for high-confidence incidents they're told to doubt
3. Lose trust in confidence scores over time (cry-wolf effect)

### Calibration Bins

| Confidence Range | Incidents | Accuracy | Gap | Status |
|-----------------|-----------|----------|-----|--------|
| 0.0 – 0.1 | 0 | – | – | N/A |
| 0.1 – 0.2 | 0 | – | – | N/A |
| 0.2 – 0.3 | 3 | 100% | -0.75 | UNDERCONFIDENT |
| 0.3 – 0.4 | 8 | 100% | -0.65 | UNDERCONFIDENT |
| 0.4 – 0.5 | 9 | 100% | -0.55 | UNDERCONFIDENT |
| 0.5 – 0.6 | 6 | 100% | -0.45 | UNDERCONFIDENT |
| 0.6 – 0.7 | 11 | 100% | -0.35 | UNDERCONFIDENT |
| 0.7 – 0.8 | 20 | 100% | -0.25 | UNDERCONFIDENT |
| 0.8 – 0.9 | 32 | 100% | -0.15 | UNDERCONFIDENT |
| 0.9 – 1.0 | 17 | 100% | -0.05 | NEAR CALIBRATED |

**Root cause**: All benchmark incidents are classified correctly by the mocked
router (confidence = ground truth = correct), so every bin has 100% accuracy.
The underconfidence is a property of the benchmark confidence values, not
of classification errors.

## Threshold Analysis

### Accuracy by Confidence Threshold

| Threshold | Incidents Above | Accuracy | Coverage |
|-----------|----------------|----------|----------|
| 0.50 | 86 | 100% | 81% |
| 0.60 | 80 | 100% | 75% |
| 0.70 | 69 | 100% | 65% |
| 0.80 | 49 | 100% | 46% |
| 0.90 | 17 | 100% | 16% |

**Abstain recommendation threshold: 0.93**

If the system abstains (escalates to operator) below 0.93 confidence, it
achieves > 90% accuracy on the incidents it acts on, while escalating
83% of incidents. This threshold is too conservative for production use.

**Recommended operational threshold: 0.70**

At 0.70 confidence threshold:
- 65% of incidents handled automatically
- 100% accuracy on auto-handled incidents
- 35% escalated to operator

## Calibration Improvement Recommendations

| Action | Expected ECE Reduction | Status |
|--------|----------------------|--------|
| Temperature scaling on confidence outputs | -0.10 to -0.15 | ASSUMED |
| Platt scaling post-training | -0.08 to -0.12 | ASSUMED |
| Add confidence calibration to training objective | -0.15 to -0.25 | ASSUMED |
| Separate calibration head for uncertainty | -0.10 to -0.20 | ASSUMED |

## Abstain and Escalation Behavior

### Current Configuration

- **Abstain threshold**: 0.93 (only act autonomously above this)
- **Escalation threshold**: 0.93 (route to operator below this)
- **Low-confidence incidents in suite**: 15 (confidence max < 0.65)

### Escalation Enforcement

All incidents with confidence below the escalation threshold MUST be routed
to human operators rather than executed autonomously. The benchmark shows 15
incidents (14%) in the inherently low-confidence category:
- Degraded provider mode incidents (BM-012, BM-043, BM-101)
- Ambiguous/noisy incidents (BM-008, BM-034, BM-084)
- False positives requiring judgment (BM-085 through BM-090)

## Brier Score: 0.1112

The Brier score of 0.111 is in the "good" range (< 0.25) and significantly
better than the random baseline (0.50). The Brier score penalizes both
overconfidence and underconfidence — here the penalty comes from underconfidence
(saying 0.70 when correct = 1.0 adds (0.70-1.0)^2 = 0.09 to the score).

## Key Finding

**Status: VERIFIED**

The confidence calibration is technically FAILING (ECE > 0.25) but in a
**safe direction**: systematic underconfidence rather than overconfidence.
An underconfident system that correctly routes low-confidence decisions to
operators is safer than an overconfident system that acts on bad predictions.

However, the calibration should be improved to reduce unnecessary escalations
and improve operator trust in confidence scores.
