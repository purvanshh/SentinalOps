import hashlib
import json
import uuid
import warnings
from typing import Any

import structlog
from db.models.workflow_checkpoint import WorkflowCheckpoint
from db.session import SessionLocal
from sqlalchemy import select

logger = structlog.get_logger(__name__)


class WorkflowCheckpointStore:
    @staticmethod
    def _state_hash(state: dict[str, Any]) -> str:
        payload = json.dumps(state, sort_keys=True, separators=(",", ":"), default=str)
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
            for checkpoint in result.scalars().all():
                if checkpoint.state_hash == self._state_hash(checkpoint.state):
                    return checkpoint
                logger.warning(
                    "checkpoint_corruption_detected",
                    thread_id=thread_id,
                    checkpoint_id=str(getattr(checkpoint, "id", "unknown")),
                    node_name=getattr(checkpoint, "node_name", "unknown"),
                )
            return None

    async def latest_for_incident(self, incident_id: str) -> WorkflowCheckpoint | None:
        """Return the most recent verified checkpoint for an incident across all threads."""
        async with SessionLocal() as session:
            result = await session.execute(
                select(WorkflowCheckpoint)
                .where(WorkflowCheckpoint.incident_id == uuid.UUID(incident_id))
                .order_by(WorkflowCheckpoint.created_at.desc())
            )
            for checkpoint in result.scalars().all():
                if checkpoint.state_hash == self._state_hash(checkpoint.state):
                    return checkpoint
                logger.warning(
                    "checkpoint_corruption_detected",
                    incident_id=incident_id,
                    checkpoint_id=str(getattr(checkpoint, "id", "unknown")),
                    node_name=getattr(checkpoint, "node_name", "unknown"),
                )
            return None

    async def recover_state(
        self, *, thread_id: str | None = None, incident_id: str | None = None
    ) -> dict[str, Any] | None:
        checkpoint = None
        if thread_id is not None:
            checkpoint = await self.latest(thread_id)
        if checkpoint is None and incident_id is not None:
            checkpoint = await self.latest_for_incident(incident_id)
        return dict(checkpoint.state) if checkpoint is not None else None


def build_langgraph_checkpointer():
    """
    Build a LangGraph checkpointer, falling back through options:
      1. AsyncPostgresSaver (durable, cross-process) — requires langgraph-checkpoint-postgres
      2. MemorySaver (in-process only) — built into langgraph; enables interrupt_before
      3. None — interrupts disabled; log a critical warning

    For production multi-process deployments, add langgraph-checkpoint-postgres
    to ensure cross-process interrupt/resume works correctly.
    """
    try:
        from core.config import get_settings
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        settings = get_settings()
        saver = AsyncPostgresSaver.from_conn_string(
            settings.database_url.replace("+psycopg", ""),
        )
        logger.info("langgraph_checkpointer", backend="AsyncPostgresSaver")
        return saver
    except ImportError:
        logger.warning(
            "langgraph_checkpointer_fallback",
            reason="langgraph-checkpoint-postgres not installed",
            backend="MemorySaver",
        )
    except Exception as exc:
        logger.warning(
            "langgraph_checkpointer_fallback",
            reason=str(exc),
            backend="MemorySaver",
        )

    try:
        from langgraph.checkpoint.memory import MemorySaver

        warnings.warn(
            "Using MemorySaver for LangGraph checkpointing. "
            "interrupt_before works within a single process only. "
            "Add langgraph-checkpoint-postgres for durable cross-process resume.",
            RuntimeWarning,
            stacklevel=2,
        )
        return MemorySaver()
    except ImportError:
        logger.critical(
            "langgraph_checkpointer_unavailable",
            reason="MemorySaver import failed; interrupt_before will not work",
        )
        return None
