from db.repositories.incident_repo import IncidentRepository


async def record_fallback(incident_id: str, session, node_name: str, error: Exception) -> None:
    repository = IncidentRepository(session)
    await repository.create_agent_execution(
        incident_id=incident_id,
        agent_name=f"{node_name}_fallback",
        input_payload={"node_name": node_name},
        output_payload={"error": str(error)},
        status="failed"
    )
