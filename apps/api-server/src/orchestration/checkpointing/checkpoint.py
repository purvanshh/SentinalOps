import uuid
from typing import Any

from sqlalchemy import select

from db.models.workflow_checkpoint import WorkflowCheckpoint
from db.session import SessionLocal


class WorkflowCheckpointStore:
    async def save(
        self,
        *,
        thread_id: str,
        incident_id: str,
        node_name: str,
        status: str,
        state: dict[str, Any],
    ) -> WorkflowCheckpoint:
        async with SessionLocal() as session:
            row = WorkflowCheckpoint(
                thread_id=thread_id,
                incident_id=uuid.UUID(incident_id),
                node_name=node_name,
                status=status,
                state=state,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def latest(self, thread_id: str) -> WorkflowCheckpoint | None:
        async with SessionLocal() as session:
            result = await session.execute(
                select(WorkflowCheckpoint)
                .where(WorkflowCheckpoint.thread_id == thread_id)
                .order_by(WorkflowCheckpoint.created_at.desc())
            )
            return result.scalars().first()
