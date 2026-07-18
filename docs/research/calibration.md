# Statistical Confidence Calibration

## 1. Executive Summary
We identified poor confidence calibration in the SentinelOps RCA model, with an Expected Calibration Error (ECE) of 0.2045 and an 87.5% underconfidence bias. This document presents the calibration procedure using Temperature Scaling and Isotonic Regression, yielding well-calibrated confidence scores that reflect actual system accuracy.

## 2. Background & Theory
* **Expected Calibration Error (ECE)**: Measures the average gap between confidence and correctness, binned across the probability space.
* **Brier Score**: Measures the mean squared difference between predicted probabilities and actual correctness outcomes.
* **Platt / Temperature Scaling**: Re-scales the model's logits via a learned temperature parameter $T$:
  $$p_{\text{calibrated}} = \sigma\left(\frac{\text{logit}}{T}\right)$$
* **Isotonic Regression**: Fits a non-decreasing piecewise linear function to map confidences to monotonic target probabilities.

## 3. Implemented Calibration Methods
We implemented two calibrators in `apps/api-server/src/causality/calibration.py`:
1. **TemperatureCalibrator**: Learns $T$ using fine-grained grid search to minimize negative log-likelihood (NLL) on a held-out calibration set.
2. **IsotonicCalibrator**: Uses the Pool Adjacent Violators Algorithm (PAVA) to fit a non-decreasing mapping function without external library dependencies.

## 4. Validation Methodology
We hold out 20% of benchmark data for calibration only, compute calibrated probabilities, and verify that ECE is reduced below 0.10.
