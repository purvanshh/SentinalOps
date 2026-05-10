import asyncio
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from db.session import SessionLocal
from db.repositories.incident_repo import IncidentRepository
from orchestration.graphs.main_graph import build_main_graph

router = APIRouter()


@router.websocket("/ws/incidents/{incident_id}/stream")
async def incident_stream(websocket: WebSocket, incident_id: UUID) -> None:
    await websocket.accept()
    try:
        while True:
            async with SessionLocal() as session:
                incident = await IncidentRepository(session).get(incident_id)
                if incident is None:
                    await websocket.send_json({"error": "Incident not found"})
                    break
                payload = {
                    "incident_id": str(incident_id),
                    "status": incident.status,
                    "thread_id": incident.graph_thread_id,
                }
                if incident.graph_thread_id:
                    payload["graph_state"] = await build_main_graph().get_state(incident.graph_thread_id)
                await websocket.send_json(payload)
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        return
