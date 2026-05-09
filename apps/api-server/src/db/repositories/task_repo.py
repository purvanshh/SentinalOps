from uuid import UUID

from sqlalchemy import select

from db.models import PendingTask
from db.repositories import BaseRepository


class PendingTaskRepository(BaseRepository):
    async def create_pending_task(
        self,
        *,
        incident_id: UUID,
        task_name: str,
        payload: dict,
        status: str = "pending",
        last_error: str | None = None,
    ) -> PendingTask:
        existing = await self.get_pending_task(incident_id, task_name)
        if existing is not None:
            existing.payload = payload
            existing.status = status
            existing.last_error = last_error
            await self.session.commit()
            await self.session.refresh(existing)
            return existing

        row = PendingTask(
            incident_id=incident_id,
            task_name=task_name,
            payload=payload,
            status=status,
            last_error=last_error,
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def get_pending_task(self, incident_id: UUID, task_name: str) -> PendingTask | None:
        result = await self.session.execute(
            select(PendingTask).where(
                PendingTask.incident_id == incident_id,
                PendingTask.task_name == task_name,
                PendingTask.status.in_(["pending", "failed"]),
            )
        )
        return result.scalar_one_or_none()

    async def list_pending_tasks(self, task_name: str | None = None) -> list[PendingTask]:
        query = select(PendingTask).where(PendingTask.status.in_(["pending", "failed"]))
        if task_name:
            query = query.where(PendingTask.task_name == task_name)
        result = await self.session.execute(query.order_by(PendingTask.created_at.asc()))
        return list(result.scalars().all())

    async def mark_running(self, task_id) -> PendingTask | None:
        row = await self.session.get(PendingTask, task_id)
        if row is None:
            return None
        row.status = "running"
        row.attempts += 1
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def mark_completed(self, task_id) -> PendingTask | None:
        row = await self.session.get(PendingTask, task_id)
        if row is None:
            return None
        row.status = "completed"
        row.last_error = None
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def mark_failed(self, task_id, error: str) -> PendingTask | None:
        row = await self.session.get(PendingTask, task_id)
        if row is None:
            return None
        row.status = "failed"
        row.last_error = error
        await self.session.commit()
        await self.session.refresh(row)
        return row
