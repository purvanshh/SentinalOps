from db.models import AuditLog
from db.repositories import BaseRepository


class AuditLogRepository(BaseRepository):
    async def create_event(
        self,
        *,
        event_type: str,
        target: str,
        outcome: str,
        incident_id=None,
        actor_id: str | None = None,
        details: dict | None = None,
    ) -> AuditLog:
        row = AuditLog(
            incident_id=incident_id,
            event_type=event_type,
            actor_id=actor_id,
            target=target,
            outcome=outcome,
            details=details or {},
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row
