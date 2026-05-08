import structlog

from observability.logging import configure_logging


def record_node_callback(node_name: str) -> None:
    configure_logging()
    structlog.get_logger("workflow").info("workflow_node_executed", node_name=node_name)
