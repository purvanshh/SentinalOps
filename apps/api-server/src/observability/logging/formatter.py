from __future__ import annotations

import logging
from contextvars import ContextVar

import structlog

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
incident_id_var: ContextVar[str | None] = ContextVar("incident_id", default=None)
thread_id_var: ContextVar[str | None] = ContextVar("thread_id", default=None)
agent_var: ContextVar[str | None] = ContextVar("agent", default=None)
execution_id_var: ContextVar[str | None] = ContextVar("execution_id", default=None)


def _inject_context(_: object, __: str, event_dict: dict) -> dict:
    for field, value in {
        "request_id": request_id_var.get(),
        "incident_id": incident_id_var.get(),
        "thread_id": thread_id_var.get(),
        "agent": agent_var.get(),
        "execution_id": execution_id_var.get(),
    }.items():
        if value:
            event_dict[field] = value
    return event_dict


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            _inject_context,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    )


def bind_request_id(request_id: str | None) -> None:
    request_id_var.set(request_id)


def bind_incident_context(
    *,
    incident_id: str | None = None,
    thread_id: str | None = None,
    agent: str | None = None,
    execution_id: str | None = None,
) -> None:
    incident_id_var.set(incident_id)
    thread_id_var.set(thread_id)
    agent_var.set(agent)
    if execution_id is not None:
        execution_id_var.set(execution_id)


def bind_execution_id(execution_id: str | None) -> None:
    execution_id_var.set(execution_id)
