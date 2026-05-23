"""Deterministic runtime — seed enforcement and hidden-randomness detection."""

from __future__ import annotations

import hashlib
import random
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Generator


@dataclass
class RuntimeSeed:
    seed: int
    derived_from: str
    created_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "derived_from": self.derived_from,
            "created_at": self.created_at,
        }


class DeterministicRuntime:
    """Enforce seed-based determinism and detect sources of hidden randomness.

    Usage:
        runtime = DeterministicRuntime(seed=42)
        with runtime.deterministic_context():
            # all random calls here are seeded
            result = run_benchmark(...)
        assert runtime.verify_no_hidden_randomness(result_a, result_b)
    """

    def __init__(self, seed: int = 42) -> None:
        self._seed = seed
        self._active_seed: RuntimeSeed | None = None

    def make_seed(self, run_id: str) -> RuntimeSeed:
        derived = int(hashlib.sha256(f"{run_id}:{self._seed}".encode()).hexdigest(), 16) % (2**32)
        seed = RuntimeSeed(
            seed=derived,
            derived_from=run_id,
            created_at=time.time(),
        )
        self._active_seed = seed
        return seed

    @contextmanager
    def deterministic_context(self, run_id: str = "default") -> Generator[RuntimeSeed, None, None]:
        seed = self.make_seed(run_id)
        random.seed(seed.seed)
        try:
            yield seed
        finally:
            random.seed(None)

    def verify_no_hidden_randomness(
        self, result_a: Any, result_b: Any, tolerance: float = 0.0
    ) -> dict[str, Any]:
        """Compare two run results for bitwise equality (tolerance=0) or near-equality."""
        import json

        serialized_a = json.dumps(result_a, sort_keys=True, default=str)
        serialized_b = json.dumps(result_b, sort_keys=True, default=str)

        if tolerance == 0.0:
            identical = serialized_a == serialized_b
            return {
                "deterministic": identical,
                "hidden_randomness_detected": not identical,
                "checksum_a": hashlib.sha256(serialized_a.encode()).hexdigest()[:12],
                "checksum_b": hashlib.sha256(serialized_b.encode()).hexdigest()[:12],
            }

        # Numeric tolerance — compare numeric leaves
        diff = self._numeric_diff(result_a, result_b)
        within_tolerance = all(abs(v) <= tolerance for v in diff.values())
        return {
            "deterministic": within_tolerance,
            "hidden_randomness_detected": not within_tolerance,
            "max_deviation": max((abs(v) for v in diff.values()), default=0.0),
            "deviations": diff,
        }

    def detect_time_dependency(
        self, results: list[Any], max_variance: float = 0.01
    ) -> dict[str, Any]:
        """Run the same nominal operation multiple times and check variance."""
        import json

        checksums = [
            hashlib.sha256(json.dumps(r, sort_keys=True, default=str).encode()).hexdigest()[:12]
            for r in results
        ]
        unique = set(checksums)
        return {
            "runs": len(results),
            "unique_outputs": len(unique),
            "deterministic": len(unique) == 1,
            "time_dependency_suspected": len(unique) > 1,
            "checksums": checksums,
        }

    @property
    def active_seed(self) -> RuntimeSeed | None:
        return self._active_seed

    def _numeric_diff(self, a: Any, b: Any, prefix: str = "") -> dict[str, float]:
        diffs: dict[str, float] = {}
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            diffs[prefix or "root"] = float(a) - float(b)
        elif isinstance(a, dict) and isinstance(b, dict):
            for k in set(a) | set(b):
                sub = self._numeric_diff(a.get(k), b.get(k), f"{prefix}.{k}" if prefix else k)
                diffs.update(sub)
        elif isinstance(a, list) and isinstance(b, list):
            for i, (x, y) in enumerate(zip(a, b, strict=False)):
                sub = self._numeric_diff(x, y, f"{prefix}[{i}]")
                diffs.update(sub)
        return diffs
