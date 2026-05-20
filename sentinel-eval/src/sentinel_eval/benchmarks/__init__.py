"""Benchmark suite and runner."""

from typing import Any


class BenchmarkSuite:
    """Loads and runs benchmark incident sets."""

    def load(self, path: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    def run(self) -> dict[str, Any]:
        raise NotImplementedError


class BenchmarkRunner:
    """Executes benchmarks against the pipeline."""

    def execute(self, suite: BenchmarkSuite) -> dict[str, Any]:
        raise NotImplementedError
