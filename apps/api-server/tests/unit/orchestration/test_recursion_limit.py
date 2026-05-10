from orchestration.graphs.main_graph import route_after_router


def test_route_after_router_moves_to_triage_when_steps_exhausted() -> None:
    next_node = route_after_router({"remaining_steps": 0, "status": "classified"})

    assert next_node == "triage"
