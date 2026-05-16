"""Operational dependency validator — checks runtime dependency availability."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DependencyStatus:
    name: str
    required: bool
    available: bool
    version: str
    health: str  # "healthy", "degraded", "unavailable", "unknown"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "required": self.required,
            "available": self.available,
            "version": self.version,
            "health": self.health,
            "notes": self.notes,
        }


@dataclass
class DependencyReport:
    all_required_available: bool
    failed_required: list[str]
    degraded_optional: list[str]
    statuses: list[DependencyStatus]
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "all_required_available": self.all_required_available,
            "failed_required": self.failed_required,
            "degraded_optional": self.degraded_optional,
            "statuses": [s.to_dict() for s in self.statuses],
            "recommendation": self.recommendation,
        }


class OperationalDependencyValidator:
    """Validate that runtime dependencies are present, healthy, and correctly versioned.

    Does not assume availability — explicitly checks each dependency and
    reports degraded/unavailable status honestly.
    """

    def validate(self, dependency_manifest: list[dict[str, Any]]) -> DependencyReport:
        statuses = [self._check(dep) for dep in dependency_manifest]

        failed_required = [s.name for s in statuses if s.required and not s.available]
        degraded_optional = [s.name for s in statuses if not s.required and s.health == "degraded"]

        all_ok = len(failed_required) == 0
        recommendation = self._recommendation(failed_required, degraded_optional)

        return DependencyReport(
            all_required_available=all_ok,
            failed_required=failed_required,
            degraded_optional=degraded_optional,
            statuses=statuses,
            recommendation=recommendation,
        )

    def validate_from_imports(self) -> DependencyReport:
        """Check Python-importable dependencies directly."""
        manifest = [
            {"name": "langchain_core", "required": True, "min_version": "0.1.0"},
            {"name": "langgraph", "required": True, "min_version": "0.1.0"},
            {"name": "fastapi", "required": True, "min_version": "0.100.0"},
            {"name": "pydantic", "required": True, "min_version": "2.0.0"},
            {"name": "openai", "required": False, "min_version": "1.0.0"},
            {"name": "anthropic", "required": False, "min_version": "0.20.0"},
            {"name": "pytest", "required": False, "min_version": "7.0.0"},
        ]
        return self.validate(manifest)

    def _check(self, dep: dict[str, Any]) -> DependencyStatus:
        name = dep["name"]
        required = bool(dep.get("required", False))
        min_version = dep.get("min_version", "0.0.0")

        try:
            import importlib.metadata

            version = importlib.metadata.version(name.replace("_", "-"))
            available = True
            health = self._check_version(version, min_version)
            notes = f"version={version}"
        except Exception:
            # Try with underscores
            try:
                import importlib.metadata

                version = importlib.metadata.version(name.replace("-", "_"))
                available = True
                health = self._check_version(version, min_version)
                notes = f"version={version}"
            except Exception as e:
                available = False
                version = "not_installed"
                health = "unavailable"
                notes = str(e)

        return DependencyStatus(
            name=name,
            required=required,
            available=available,
            version=version,
            health=health,
            notes=notes,
        )

    def _check_version(self, installed: str, minimum: str) -> str:
        try:
            from packaging.version import Version  # type: ignore[import-untyped]

            if Version(installed) >= Version(minimum):
                return "healthy"
            return "degraded"
        except Exception:
            return "unknown"

    def _recommendation(self, failed: list[str], degraded: list[str]) -> str:
        if not failed and not degraded:
            return "All dependencies satisfied. System is dependency-ready."
        if failed:
            return f"BLOCKING: Missing required dependencies: {', '.join(failed)}. System cannot start."
        return f"WARNING: Optional dependencies degraded: {', '.join(degraded)}. Some features may be unavailable."
