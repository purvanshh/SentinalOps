"""Safety engine, tool allowlists, and risk classification."""

from dataclasses import dataclass


class SafetyEngine:
    """Validates actions before execution."""

    def check_action(self, action: str, context: dict) -> bool:
        raise NotImplementedError

    def validate_tool_call(self, tool_name: str, args: dict) -> bool:
        raise NotImplementedError


class ToolAllowlist:
    """Manages allowed tools per risk tier."""

    def is_allowed(self, tool_name: str, risk_tier: str) -> bool:
        raise NotImplementedError

    def get_allowed_tools(self, risk_tier: str) -> list[str]:
        raise NotImplementedError


class RiskClassifier:
    """Classifies incident and action risk levels."""

    def classify(self, action: str, context: dict) -> str:
        raise NotImplementedError

    def get_risk_level(self, incident: dict) -> str:
        raise NotImplementedError
