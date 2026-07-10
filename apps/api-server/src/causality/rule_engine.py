from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import yaml


@dataclass
class CausalRule:
    id: str
    category: str
    description: str
    conditions: list[dict[str, Any]]
    mechanism_type: str
    confidence: float
    source: str


@dataclass
class RuleMatch:
    rule: CausalRule
    confidence: float
    matched_evidence: list[str] = field(default_factory=list)


class RuleEngine:
    def __init__(self, rules_path: str | None = None) -> None:
        if not rules_path:
            # Go up until we find the config or reach root
            current = os.path.abspath(__file__)
            for _ in range(6):
                current = os.path.dirname(current)
                candidate = os.path.join(current, "configs", "production", "causality_rules.yaml")
                if os.path.exists(candidate):
                    rules_path = candidate
                    break
            if not rules_path:
                rules_path = "configs/production/causality_rules.yaml"

        self.rules: list[CausalRule] = []
        if os.path.exists(rules_path):
            with open(rules_path) as f:
                data = yaml.safe_load(f)
                for r in data.get("rules", []):
                    self.rules.append(
                        CausalRule(
                            id=r["id"],
                            category=r["category"],
                            description=r["description"],
                            conditions=r["conditions"],
                            mechanism_type=r["mechanism_type"],
                            confidence=float(r["confidence"]),
                            source=r["source"],
                        )
                    )

    def evaluate(self, evidence_items: list[dict[str, Any]]) -> list[RuleMatch]:
        matches = []
        for rule in self.rules:
            # Check all conditions of the rule. All must match (AND).
            rule_matched = True
            all_matched_keys: set[str] = set()

            for cond in rule.conditions:
                cond_matched, matched_keys = self._check_condition(cond, evidence_items)
                if not cond_matched:
                    rule_matched = False
                    break
                all_matched_keys.update(matched_keys)

            if rule_matched:
                matches.append(
                    RuleMatch(
                        rule=rule,
                        confidence=rule.confidence,
                        matched_evidence=sorted(list(all_matched_keys)),
                    )
                )

        return self.resolve_conflicts(matches)

    def _check_condition(
        self, condition: dict[str, Any], evidence_items: list[dict[str, Any]]
    ) -> tuple[bool, list[str]]:
        # A condition dict is matched if there is at least one evidence item that
        # matches all of its sub-criteria.
        matched_keys = []
        for item in evidence_items:
            item_match = True

            # Check signal_contains
            if "signal_contains" in condition:
                signal = str(item.get("signal") or item.get("item_key") or "").lower()
                if not any(sub in signal for sub in condition["signal_contains"]):
                    item_match = False

            # Check severity_in
            if "severity_in" in condition:
                severity = str(item.get("severity") or "").lower()
                if severity not in condition["severity_in"]:
                    item_match = False

            # Check source_in
            if "source_in" in condition:
                source = str(item.get("source") or "").lower()
                if source not in condition["source_in"]:
                    item_match = False

            if item_match:
                item_key = item.get("item_key") or item.get("evidence_id") or "unknown"
                matched_keys.append(item_key)

        return len(matched_keys) > 0, matched_keys

    def resolve_conflicts(self, matches: list[RuleMatch]) -> list[RuleMatch]:
        if len(matches) <= 1:
            return matches

        # Find distinct mechanism types
        mechanism_types = {m.rule.mechanism_type for m in matches}
        if len(mechanism_types) > 1:
            # Conflicts found! Disagreement on mechanism type -> multiply all confidences by 0.8
            for m in matches:
                m.confidence = round(m.confidence * 0.8, 4)

        return matches
