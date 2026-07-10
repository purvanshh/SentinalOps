from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any


def pava(y: list[float]) -> list[float]:
    n = len(y)
    if n == 0:
        return []
    # Target values/predictions (non-decreasing)
    # Maintain blocks of (value, weight, start_idx, end_idx)
    blocks: list[list[Any]] = [[y[i], 1.0, i, i] for i in range(n)]

    while True:
        violation = False
        for i in range(len(blocks) - 1):
            if blocks[i][0] > blocks[i + 1][0]:
                # Merge blocks
                new_val = (blocks[i][0] * blocks[i][1] + blocks[i + 1][0] * blocks[i + 1][1]) / (
                    blocks[i][1] + blocks[i + 1][1]
                )
                new_weight = blocks[i][1] + blocks[i + 1][1]
                new_start = blocks[i][2]
                new_end = blocks[i + 1][3]
                blocks[i] = [new_val, new_weight, new_start, new_end]
                del blocks[i + 1]
                violation = True
                break
        if not violation:
            break

    res = [0.0] * n
    for val, _, start, end in blocks:
        for i in range(start, end + 1):
            res[i] = val
    return res


class IsotonicCalibrator:
    def __init__(self) -> None:
        self._x: list[float] = []
        self._y: list[float] = []
        self._fitted = False

    @property
    def fitted(self) -> bool:
        return self._fitted

    def fit(self, confidences: list[float], correctness: list[bool]) -> None:
        if not confidences:
            self._x = []
            self._y = []
            self._fitted = True
            return

        # Group correctness values by confidence
        grouped: dict[float, list[float]] = {}
        for conf, corr in zip(confidences, correctness, strict=False):
            val = 1.0 if corr else 0.0
            if conf not in grouped:
                grouped[conf] = []
            grouped[conf].append(val)

        x_unique = sorted(grouped.keys())
        y_avg = [sum(grouped[x]) / len(grouped[x]) for x in x_unique]
        y_isotonic = pava(y_avg)

        self._x = x_unique
        self._y = y_isotonic
        self._fitted = True

    def predict(self, confidence: float) -> float:
        if not self._fitted or not self._x:
            return confidence

        # Handle boundaries
        if confidence <= self._x[0]:
            return self._y[0]
        if confidence >= self._x[-1]:
            return self._y[-1]

        # Linear interpolation
        for i in range(len(self._x) - 1):
            if self._x[i] <= confidence <= self._x[i + 1]:
                t = (confidence - self._x[i]) / (self._x[i + 1] - self._x[i])
                return round(self._y[i] + t * (self._y[i + 1] - self._y[i]), 4)

        return confidence


class TemperatureCalibrator:
    def __init__(self) -> None:
        self._temperature = 1.0
        self._fitted = False

    @property
    def temperature(self) -> float:
        return self._temperature

    @property
    def fitted(self) -> bool:
        return self._fitted

    def fit(self, confidences: list[float], correctness: list[bool]) -> None:
        if not confidences:
            self._temperature = 1.0
            self._fitted = True
            return

        best_t = 1.0
        min_nll = float("inf")

        # Grid search over T (0.05 to 5.0)
        for step in range(1, 101):
            t = step / 20.0
            nll = 0.0
            for conf, corr in zip(confidences, correctness, strict=False):
                y = 1.0 if corr else 0.0
                bounded = min(max(conf, 1e-6), 1.0 - 1e-6)
                logit = math.log(bounded / (1.0 - bounded))
                scaled = 1.0 / (1.0 + math.exp(-(logit / t)))
                scaled_bounded = min(max(scaled, 1e-6), 1.0 - 1e-6)
                nll -= y * math.log(scaled_bounded) + (1.0 - y) * math.log(1.0 - scaled_bounded)

            if nll < min_nll:
                min_nll = nll
                best_t = t

        self._temperature = round(best_t, 4)
        self._fitted = True

    def predict(self, confidence: float) -> float:
        if not self._fitted:
            return confidence
        bounded = min(max(confidence, 1e-6), 1.0 - 1e-6)
        logit = math.log(bounded / (1.0 - bounded))
        scaled = 1.0 / (1.0 + math.exp(-(logit / self._temperature)))
        return round(min(max(scaled, 0.0), 1.0), 4)


@dataclass
class CalibrationSplit:
    train_confidences: list[float]
    train_correctness: list[bool]
    cal_confidences: list[float]
    cal_correctness: list[bool]
    test_confidences: list[float]
    test_correctness: list[bool]


def split_calibration_data(
    confidences: list[float],
    correctness: list[bool],
    cal_fraction: float = 0.2,
    seed: int = 42,
) -> CalibrationSplit:
    n = len(confidences)
    indices = list(range(n))
    rng = random.Random(seed)
    rng.shuffle(indices)

    cal_size = int(n * cal_fraction)
    test_size = int(n * cal_fraction)
    train_size = n - cal_size - test_size

    train_idx = indices[:train_size]
    cal_idx = indices[train_size : train_size + cal_size]
    test_idx = indices[train_size + cal_size :]

    return CalibrationSplit(
        train_confidences=[confidences[i] for i in train_idx],
        train_correctness=[correctness[i] for i in train_idx],
        cal_confidences=[confidences[i] for i in cal_idx],
        cal_correctness=[correctness[i] for i in cal_idx],
        test_confidences=[confidences[i] for i in test_idx],
        test_correctness=[correctness[i] for i in test_idx],
    )


def build_reliability_diagram_data(
    confidences: list[float], correctness: list[bool], n_bins: int = 10
) -> list[dict[str, Any]]:
    bin_size = 1.0 / n_bins
    diagram = []
    for i in range(n_bins):
        low = i * bin_size
        high = (i + 1) * bin_size
        in_bin = [
            (c, ok)
            for c, ok in zip(confidences, correctness, strict=False)
            if low <= c < high or (i == n_bins - 1 and c == 1.0)
        ]
        count = len(in_bin)
        if count > 0:
            accuracy = sum(1 for _, ok in in_bin if ok) / count
            avg_conf = sum(c for c, _ in in_bin) / count
            diagram.append(
                {
                    "bin_center": round(low + bin_size / 2, 4),
                    "accuracy": round(accuracy, 4),
                    "confidence": round(avg_conf, 4),
                    "count": count,
                }
            )
    return diagram
