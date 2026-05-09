import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import select

from db.models.workflow_checkpoint import WorkflowCheckpoint
from db.session import SessionLocal


class WorkflowCheckpointStore:
    @staticmethod
    def _state_hash(state: dict[str, Any]) -> str:
        payload = json.dumps(state, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

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
                state_hash=self._state_hash(state),
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
            checkpoints = list(result.scalars().all())
            for checkpoint in checkpoints:
                if checkpoint.state_hash == self._state_hash(checkpoint.state):
                    return checkpoint
            return None


def build_langgraph_checkpointer():
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    except Exception:  # noqa: BLE001
        return None

    from core.config import get_settings

    settings = get_settings()
    return AsyncPostgresSaver.from_conn_string(
        settings.database_url.replace("+psycopg", ""),
    )
