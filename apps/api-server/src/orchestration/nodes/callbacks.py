from observability.logging import configure_logging


def record_node_callback(node_name: str) -> None:
    configure_logging()
    _ = node_name
