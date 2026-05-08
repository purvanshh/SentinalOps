class SentinelOpsError(Exception):
    """Base application exception."""


class AgentTimeoutError(SentinelOpsError):
    """Raised when an agent exceeds its allowed execution window."""


class ToolFailureError(SentinelOpsError):
    """Raised when a required tool call fails."""


class StateCorruptionError(SentinelOpsError):
    """Raised when persisted workflow state cannot be trusted."""
