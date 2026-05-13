from datetime import datetime, timedelta, timezone
from uuid import UUID

from db.models import PendingTask
from db.repositories import BaseRepository
from sqlalchemy import select


class PendingTaskRepository(BaseRepository):
    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _build_recovery_metadata(
        self, row: PendingTask | None, *, payload: dict | None = None
    ) -> dict:
        source = payload if payload is not None else (row.payload if row is not None else {})
        recovery = dict(source.get("recovery", {}))
        recovery.setdefault("execution_lineage", [])
        recovery.setdefault("replay_count", 0)
        recovery.setdefault("last_stage", "queued")
        recovery.setdefault("lease_owner", None)
        recovery.setdefault("last_heartbeat_at", None)
        recovery.setdefault("last_replay_reason", None)
        recovery.setdefault("last_transition_at", self._now_iso())
        return recovery

    def _merge_payload(self, row: PendingTask | None, payload: dict, *, recovery: dict) -> dict:
        merged = dict(row.payload if row is not None else {})
        merged.update(payload)
        merged["recovery"] = recovery
        return merged

    async def create_pending_task(
        self,
        *,
        incident_id: UUID,
        task_name: str,
        payload: dict,
        status: str = "pending",
        last_error: str | None = None,
    ) -> PendingTask:
        existing = await self.get_task(incident_id, task_name)
        if existing is not None and existing.status not in {"completed", "dead_letter"}:
            recovery = self._build_recovery_metadata(existing, payload=payload)
            recovery["last_transition_at"] = self._now_iso()
            if last_error is not None:
                recovery["last_error"] = last_error
            existing.payload = self._merge_payload(existing, payload, recovery=recovery)
            existing.status = status
            existing.last_error = last_error
            await self.session.commit()
            await self.session.refresh(existing)
            return existing

        recovery = self._build_recovery_metadata(None, payload=payload)
        recovery["last_transition_at"] = self._now_iso()
        if last_error is not None:
            recovery["last_error"] = last_error

        row = PendingTask(
            incident_id=incident_id,
            task_name=task_name,
            payload={**payload, "recovery": recovery},
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

    async def get_task(self, incident_id: UUID, task_name: str) -> PendingTask | None:
        result = await self.session.execute(
            select(PendingTask).where(
                PendingTask.incident_id == incident_id,
                PendingTask.task_name == task_name,
            )
        )
        return result.scalar_one_or_none()

    async def list_pending_tasks(self, task_name: str | None = None) -> list[PendingTask]:
        query = select(PendingTask).where(PendingTask.status.in_(["pending", "failed"]))
        if task_name:
            query = query.where(PendingTask.task_name == task_name)
        result = await self.session.execute(query.order_by(PendingTask.created_at.asc()))
        return list(result.scalars().all())

    async def list_recoverable_tasks(
        self,
        task_name: str | None = None,
        *,
        stale_after_seconds: int = 30,
    ) -> list[PendingTask]:
        stale_before = datetime.now(timezone.utc) - timedelta(seconds=stale_after_seconds)
        query = select(PendingTask).where(
            PendingTask.status.in_(["pending", "failed"])
            | (
                PendingTask.status.in_(["running", "replaying"])
                & (PendingTask.updated_at <= stale_before)
            )
        )
        if task_name:
            query = query.where(PendingTask.task_name == task_name)
        result = await self.session.execute(query.order_by(PendingTask.created_at.asc()))
        return list(result.scalars().all())

    async def mark_replay_scheduled(
        self, task_id, *, replayer_id: str, reason: str
    ) -> PendingTask | None:
        row = await self.session.get(PendingTask, task_id)
        if row is None:
            return None
        recovery = self._build_recovery_metadata(row)
        recovery["replay_count"] = int(recovery.get("replay_count", 0)) + 1
        recovery["last_replay_reason"] = reason
        recovery["scheduled_by"] = replayer_id
        recovery["last_transition_at"] = self._now_iso()
        recovery["last_stage"] = "replay_scheduled"
        row.payload = self._merge_payload(row, row.payload, recovery=recovery)
        row.status = "replaying"
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def mark_running(self, task_id) -> PendingTask | None:
        row = await self.session.get(PendingTask, task_id)
        if row is None:
            return None
        row.status = "running"
        row.attempts += 1
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def mark_running_by_incident(
        self,
        incident_id: UUID,
        task_name: str,
        *,
        worker_run_id: str,
        thread_id: str | None = None,
        execution_id: str | None = None,
    ) -> PendingTask | None:
        row = await self.get_task(incident_id, task_name)
        if row is None:
            return None
        recovery = self._build_recovery_metadata(row)
        lineage = list(recovery.get("execution_lineage", []))
        lineage.append(worker_run_id)
        recovery["execution_lineage"] = lineage
        recovery["lease_owner"] = worker_run_id
        recovery["last_stage"] = "running"
        recovery["last_heartbeat_at"] = self._now_iso()
        recovery["thread_id"] = thread_id
        recovery["execution_id"] = execution_id
        recovery["last_transition_at"] = self._now_iso()
        row.payload = self._merge_payload(row, row.payload, recovery=recovery)
        row.status = "running"
        row.attempts += 1
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def heartbeat_by_incident(
        self,
        incident_id: UUID,
        task_name: str,
        *,
        worker_run_id: str,
        stage: str,
        thread_id: str | None = None,
        execution_id: str | None = None,
    ) -> PendingTask | None:
        row = await self.get_task(incident_id, task_name)
        if row is None:
            return None
        recovery = self._build_recovery_metadata(row)
        if recovery.get("lease_owner") != worker_run_id:
            return None
        recovery["last_stage"] = stage
        recovery["last_heartbeat_at"] = self._now_iso()
        recovery["thread_id"] = thread_id or recovery.get("thread_id")
        recovery["execution_id"] = execution_id or recovery.get("execution_id")
        row.payload = self._merge_payload(row, row.payload, recovery=recovery)
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

    async def mark_completed_by_incident(
        self,
        incident_id: UUID,
        task_name: str,
        *,
        final_status: str,
    ) -> PendingTask | None:
        row = await self.get_task(incident_id, task_name)
        if row is None:
            return None
        recovery = self._build_recovery_metadata(row)
        recovery["last_stage"] = final_status
        recovery["completed_at"] = self._now_iso()
        recovery["lease_owner"] = None
        recovery["last_transition_at"] = self._now_iso()
        row.payload = self._merge_payload(row, row.payload, recovery=recovery)
        row.status = "completed"
        row.last_error = None
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def mark_failed_by_incident(
        self,
        incident_id: UUID,
        task_name: str,
        error: str,
        *,
        stage: str = "failed",
    ) -> PendingTask | None:
        row = await self.get_task(incident_id, task_name)
        if row is None:
            return None
        recovery = self._build_recovery_metadata(row)
        recovery["last_stage"] = stage
        recovery["last_error"] = error
        recovery["failed_at"] = self._now_iso()
        recovery["lease_owner"] = None
        recovery["last_transition_at"] = self._now_iso()
        row.payload = self._merge_payload(row, row.payload, recovery=recovery)
        row.status = "failed"
        row.last_error = error
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

    async def mark_dead_letter(self, task_id, reason: str) -> PendingTask | None:
        row = await self.session.get(PendingTask, task_id)
        if row is None:
            return None
        recovery = self._build_recovery_metadata(row)
        recovery["last_stage"] = "dead_letter"
        recovery["dead_letter_reason"] = reason
        recovery["dead_lettered_at"] = self._now_iso()
        recovery["lease_owner"] = None
        recovery["last_transition_at"] = self._now_iso()
        row.payload = self._merge_payload(row, row.payload, recovery=recovery)
        row.status = "dead_letter"
        row.last_error = reason
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def list_dead_letter_tasks(self) -> list[PendingTask]:
        from sqlalchemy import select

        result = await self.session.execute(
            select(PendingTask)
            .where(PendingTask.status == "dead_letter")
            .order_by(PendingTask.created_at.asc())
        )
        return list(result.scalars().all())
