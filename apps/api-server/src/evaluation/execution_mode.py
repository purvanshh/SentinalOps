from __future__ import annotations

from enum import Enum


class ExecutionMode(str, Enum):
    """
    Controls side effects and external API access during agent execution.

    PRODUCTION  - Full external API access, Celery tasks, remediation execution.
    EVALUATION  - All side effects disabled; deterministic mocked infrastructure only.
                  Evaluation MUST run in this mode to ensure sandbox integrity.
    """

    PRODUCTION = "PRODUCTION"
    EVALUATION = "EVALUATION"

    @property
    def disables_side_effects(self) -> bool:
        return self == ExecutionMode.EVALUATION

    @property
    def allows_external_api_calls(self) -> bool:
        return self == ExecutionMode.PRODUCTION

    @property
    def allows_celery_tasks(self) -> bool:
        return self == ExecutionMode.PRODUCTION

    @property
    def allows_remediation_execution(self) -> bool:
        return self == ExecutionMode.PRODUCTION

    @property
    def allows_approval_escalation(self) -> bool:
        return self == ExecutionMode.PRODUCTION

    @property
    def allows_async_replay_scheduling(self) -> bool:
        return self == ExecutionMode.PRODUCTION

    @property
    def allows_outbound_notifications(self) -> bool:
        return self == ExecutionMode.PRODUCTION
