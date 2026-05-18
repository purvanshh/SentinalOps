"""Layer boundary validator — enforces architectural separation of concerns."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Allowed dependency directions. Key may depend on values — not the reverse.
_ALLOWED_DIRECTION: dict[str, list[str]] = {
    "api": ["core", "orchestration", "agents", "evaluation"],
    "orchestration": ["agents", "core", "memory", "tools"],
    "agents": ["core", "memory", "tools", "retrieval"],
    "evaluation": ["core", "replay"],
    "observability": ["core"],
    "validation": ["core"],
    "runtime": ["core", "orchestration", "evaluation"],
    "operators": ["core", "evaluation"],
    "ingestion": ["core"],
    "causality": ["core"],
    "semantics": ["core"],
}


@dataclass
class BoundaryViolation:
    source_layer: str
    target_layer: str
    module: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_layer": self.source_layer,
            "target_layer": self.target_layer,
            "module": self.module,
            "description": self.description,
        }


@dataclass
class BoundaryReport:
    violations: list[BoundaryViolation]
    layers_checked: list[str]
    clean: bool
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "violations": [v.to_dict() for v in self.violations],
            "layers_checked": self.layers_checked,
            "clean": self.clean,
            "summary": self.summary,
        }


class LayerBoundaryValidator:
    """Validate that architectural layer boundaries are respected.

    Uses import-graph heuristics based on module path naming conventions.
    A violation is when layer A imports from layer B and that direction is not
    in the allowed dependency graph.
    """

    def validate(self, src_root: Path) -> BoundaryReport:
        violations: list[BoundaryViolation] = []
        layers_found: set[str] = set()

        for py_file in src_root.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            rel = str(py_file.relative_to(src_root))
            source_layer = self._layer_from_path(rel)
            if not source_layer:
                continue
            layers_found.add(source_layer)

            imports = self._extract_local_imports(py_file)
            for imp in imports:
                target_layer = self._layer_from_import(imp)
                if target_layer and target_layer != source_layer:
                    if not self._is_allowed(source_layer, target_layer):
                        violations.append(
                            BoundaryViolation(
                                source_layer=source_layer,
                                target_layer=target_layer,
                                module=rel,
                                description=f"{source_layer} should not depend on {target_layer}",
                            )
                        )

        return BoundaryReport(
            violations=violations,
            layers_checked=sorted(layers_found),
            clean=len(violations) == 0,
            summary=self._summarize(violations, layers_found),
        )

    def _layer_from_path(self, path: str) -> str | None:
        parts = path.split("/")
        if parts:
            candidate = parts[0]
            if candidate in _ALLOWED_DIRECTION:
                return candidate
        return None

    def _layer_from_import(self, imp: str) -> str | None:
        for layer in _ALLOWED_DIRECTION:
            if imp.startswith(layer + ".") or imp == layer:
                return layer
        return None

    def _is_allowed(self, source: str, target: str) -> bool:
        return target in _ALLOWED_DIRECTION.get(source, [])

    def _extract_local_imports(self, path: Path) -> list[str]:
        import ast

        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            return []
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        return imports

    def _summarize(self, violations: list, layers: set) -> str:
        if not violations:
            return f"All layer boundaries respected across {len(layers)} layers."
        return f"{len(violations)} boundary violation(s) across {len(layers)} layers."
