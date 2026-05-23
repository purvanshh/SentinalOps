"""Dependency graph validator — detects cycles, forbidden imports, and orphan modules."""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class DependencyReport:
    cyclic_dependencies: list[list[str]]
    forbidden_imports: list[dict[str, str]]
    orphan_modules: list[str]
    total_modules: int
    dependency_edges: int
    clean: bool
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "cyclic_dependencies": self.cyclic_dependencies,
            "forbidden_imports": self.forbidden_imports,
            "orphan_modules": self.orphan_modules,
            "total_modules": self.total_modules,
            "dependency_edges": self.dependency_edges,
            "clean": self.clean,
            "summary": self.summary,
        }


_FORBIDDEN_CROSS_IMPORTS = [
    # evaluation must not import from production runtime
    {"from_layer": "evaluation", "to_layer": "runtime", "reason": "eval→runtime coupling"},
    # diagnostics must not import from evaluation scorers
    {
        "from_layer": "observability/diagnostics",
        "to_layer": "evaluation/scorers",
        "reason": ("diag→scorer coupling"),
    },
]


class DependencyGraphValidator:
    """Static analysis of Python import graph within the SentinelOps source tree.

    Checks:
    - Cyclic imports between modules
    - Forbidden cross-layer imports
    - Orphan modules (defined but never imported)
    """

    def validate(self, src_root: Path) -> DependencyReport:
        graph = self._build_graph(src_root)
        cycles = self._detect_cycles(graph)
        forbidden = self._check_forbidden(graph)
        orphans = self._detect_orphans(graph)

        clean = not cycles and not forbidden
        total = len(graph)
        edges = sum(len(v) for v in graph.values())

        summary = self._summarize(cycles, forbidden, orphans, total)
        return DependencyReport(
            cyclic_dependencies=cycles,
            forbidden_imports=forbidden,
            orphan_modules=orphans,
            total_modules=total,
            dependency_edges=edges,
            clean=clean,
            summary=summary,
        )

    def _build_graph(self, src_root: Path) -> dict[str, list[str]]:
        graph: dict[str, list[str]] = {}
        for py_file in src_root.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            module = self._path_to_module(py_file, src_root)
            imports = self._extract_imports(py_file)
            graph[module] = imports
        return graph

    def _extract_imports(self, path: Path) -> list[str]:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            return []
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
        return imports

    def _path_to_module(self, path: Path, root: Path) -> str:
        rel = path.relative_to(root)
        return str(rel).replace(os.sep, ".").removesuffix(".py")

    def _detect_cycles(self, graph: dict[str, list[str]]) -> list[list[str]]:
        visited: set[str] = set()
        path: list[str] = []
        cycles: list[list[str]] = []

        def dfs(node: str) -> None:
            if node in path:
                cycle_start = path.index(node)
                cycles.append(path[cycle_start:] + [node])
                return
            if node in visited or node not in graph:
                return
            path.append(node)
            for neighbor in graph.get(node, []):
                # Only follow intra-project imports
                if neighbor in graph:
                    dfs(neighbor)
            path.pop()
            visited.add(node)

        for module in list(graph.keys()):
            dfs(module)

        # Deduplicate
        seen: set[frozenset] = set()
        unique: list[list[str]] = []
        for cycle in cycles:
            key = frozenset(cycle)
            if key not in seen:
                seen.add(key)
                unique.append(cycle)
        return unique[:10]  # cap output for readability

    def _check_forbidden(self, graph: dict[str, list[str]]) -> list[dict[str, str]]:
        violations: list[dict[str, str]] = []
        for module, imports in graph.items():
            for rule in _FORBIDDEN_CROSS_IMPORTS:
                if rule["from_layer"] in module:
                    for imp in imports:
                        # Match only if import is exactly the target layer or starts with
                        # "target_layer." — prevents "deterministic_runtime" matching "runtime".
                        target = rule["to_layer"]
                        if imp == target or imp.startswith(target + "."):
                            violations.append(
                                {
                                    "module": module,
                                    "forbidden_import": imp,
                                    "reason": rule["reason"],
                                }
                            )
        return violations

    def _detect_orphans(self, graph: dict[str, list[str]]) -> list[str]:
        all_imported: set[str] = set()
        for imports in graph.values():
            all_imported.update(imports)
        orphans = [
            m
            for m in graph
            if m not in all_imported
            and not m.endswith("__init__")
            and not m.endswith("__main__")
            and "test" not in m.lower()
        ]
        return orphans[:20]  # cap for readability

    def _summarize(self, cycles: list, forbidden: list, orphans: list, total: int) -> str:
        if not cycles and not forbidden:
            return f"Dependency graph clean. {total} modules, {len(orphans)} potential orphans."
        issues = []
        if cycles:
            issues.append(f"{len(cycles)} cyclic dependency/ies")
        if forbidden:
            issues.append(f"{len(forbidden)} forbidden cross-layer import(s)")
        return f"Issues: {', '.join(issues)}. {total} modules analyzed."
