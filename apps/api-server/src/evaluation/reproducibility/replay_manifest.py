"""Replay manifest — version-locked, checksum-validated record of every evaluation run."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ManifestEntry:
    run_id: str
    timestamp: float
    benchmark_version: str
    dataset_checksum: str
    environment_hash: str
    seed: int
    parameters: dict[str, Any]
    result_checksum: str
    passed: bool
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "benchmark_version": self.benchmark_version,
            "dataset_checksum": self.dataset_checksum,
            "environment_hash": self.environment_hash,
            "seed": self.seed,
            "parameters": self.parameters,
            "result_checksum": self.result_checksum,
            "passed": self.passed,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ManifestEntry":
        return cls(**d)


class ReplayManifest:
    """Append-only log of benchmark runs with full provenance.

    Enables external auditors to verify that a claimed result is reproducible
    from a specific dataset snapshot and environment configuration.
    """

    MANIFEST_VERSION = "1.0"

    def __init__(self, manifest_path: Path | None = None) -> None:
        self._path = manifest_path
        self._entries: list[ManifestEntry] = []
        if manifest_path and manifest_path.exists():
            self._load(manifest_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(
        self,
        *,
        run_id: str,
        benchmark_version: str,
        dataset_checksum: str,
        environment_hash: str,
        seed: int,
        parameters: dict[str, Any],
        results: Any,
        passed: bool,
        notes: str = "",
    ) -> ManifestEntry:
        result_checksum = self._checksum(json.dumps(results, sort_keys=True, default=str))
        entry = ManifestEntry(
            run_id=run_id,
            timestamp=time.time(),
            benchmark_version=benchmark_version,
            dataset_checksum=dataset_checksum,
            environment_hash=environment_hash,
            seed=seed,
            parameters=parameters,
            result_checksum=result_checksum,
            passed=passed,
            notes=notes,
        )
        self._entries.append(entry)
        if self._path:
            self._persist()
        return entry

    def verify(self, run_id: str, results: Any) -> bool:
        """Return True if ``results`` match the recorded checksum for ``run_id``."""
        entry = self._find(run_id)
        if entry is None:
            return False
        actual = self._checksum(json.dumps(results, sort_keys=True, default=str))
        return actual == entry.result_checksum

    def detect_drift(self, run_id: str, current_dataset_checksum: str) -> bool:
        """Return True if the dataset has mutated since the manifest entry was recorded."""
        entry = self._find(run_id)
        if entry is None:
            return True
        return entry.dataset_checksum != current_dataset_checksum

    def summary(self) -> dict[str, Any]:
        total = len(self._entries)
        passed = sum(1 for e in self._entries if e.passed)
        return {
            "manifest_version": self.MANIFEST_VERSION,
            "total_runs": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": round(passed / total, 4) if total else 0.0,
            "entries": [e.to_dict() for e in self._entries],
        }

    def entries(self) -> list[ManifestEntry]:
        return list(self._entries)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find(self, run_id: str) -> ManifestEntry | None:
        for e in reversed(self._entries):
            if e.run_id == run_id:
                return e
        return None

    def _checksum(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    def _persist(self) -> None:
        assert self._path is not None
        self._path.write_text(json.dumps(self.summary(), indent=2))

    def _load(self, path: Path) -> None:
        data = json.loads(path.read_text())
        for raw in data.get("entries", []):
            self._entries.append(ManifestEntry.from_dict(raw))
