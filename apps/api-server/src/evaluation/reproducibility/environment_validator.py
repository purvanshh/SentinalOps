"""Environment validator — snapshot and compare runtime dependencies for reproducibility."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import sys
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EnvironmentReport:
    python_version: str
    platform_info: str
    package_versions: dict[str, str]
    environment_hash: str
    drift_warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "python_version": self.python_version,
            "platform_info": self.platform_info,
            "package_versions": self.package_versions,
            "environment_hash": self.environment_hash,
            "drift_warnings": self.drift_warnings,
        }


CRITICAL_PACKAGES = [
    "langchain",
    "langchain-core",
    "langgraph",
    "openai",
    "anthropic",
    "fastapi",
    "pydantic",
    "numpy",
    "pytest",
    "ruff",
    "black",
]


class EnvironmentValidator:
    """Snapshot the runtime environment and detect dependency drift between runs.

    Drift means two runs that should produce identical outputs may not,
    because underlying library behaviour changed.
    """

    def snapshot(self) -> EnvironmentReport:
        pkg_versions = self._installed_versions()
        env_hash = self._hash_env(pkg_versions)
        return EnvironmentReport(
            python_version=sys.version,
            platform_info=platform.platform(),
            package_versions=pkg_versions,
            environment_hash=env_hash,
        )

    def compare(self, baseline: EnvironmentReport, current: EnvironmentReport) -> dict[str, Any]:
        warnings: list[str] = []

        if baseline.python_version != current.python_version:
            warnings.append(f"python_version_changed:{baseline.python_version!r}->{current.python_version!r}")

        if baseline.platform_info != current.platform_info:
            warnings.append("platform_changed")

        added, removed, changed = self._diff_packages(baseline.package_versions, current.package_versions)
        for pkg in added:
            warnings.append(f"package_added:{pkg}={current.package_versions[pkg]}")
        for pkg in removed:
            warnings.append(f"package_removed:{pkg}")
        for pkg in changed:
            warnings.append(
                f"package_changed:{pkg}:{baseline.package_versions[pkg]}->{current.package_versions[pkg]}"
            )

        critical_drifted = [
            w for w in warnings
            if any(p in w for p in CRITICAL_PACKAGES)
        ]

        return {
            "clean": len(warnings) == 0,
            "total_warnings": len(warnings),
            "critical_drift": critical_drifted,
            "all_warnings": warnings,
            "hash_match": baseline.environment_hash == current.environment_hash,
        }

    def validate_against_snapshot(
        self, snapshot_path: str, strict: bool = False
    ) -> dict[str, Any]:
        import pathlib

        p = pathlib.Path(snapshot_path)
        if not p.exists():
            return {"error": "snapshot_file_not_found", "path": snapshot_path}

        data = json.loads(p.read_text())
        baseline = EnvironmentReport(**data)
        current = self.snapshot()
        result = self.compare(baseline, current)
        if strict and not result["clean"]:
            result["validation_failed"] = True
        return result

    def save_snapshot(self, path: str) -> EnvironmentReport:
        import pathlib

        report = self.snapshot()
        pathlib.Path(path).write_text(json.dumps(report.to_dict(), indent=2))
        return report

    def _installed_versions(self) -> dict[str, str]:
        versions: dict[str, str] = {}
        for dist in importlib.metadata.distributions():
            name = dist.metadata["Name"]
            version = dist.metadata["Version"]
            if name:
                versions[name.lower()] = version
        return dict(sorted(versions.items()))

    def _hash_env(self, pkg_versions: dict[str, str]) -> str:
        blob = json.dumps(pkg_versions, sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()[:16]

    def _diff_packages(
        self, a: dict[str, str], b: dict[str, str]
    ) -> tuple[list[str], list[str], list[str]]:
        added = [k for k in b if k not in a]
        removed = [k for k in a if k not in b]
        changed = [k for k in a if k in b and a[k] != b[k]]
        return added, removed, changed
