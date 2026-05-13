from datetime import UTC, datetime
from uuid import UUID

from db.models import ApprovalRequest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class ApprovalStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_approval_request(
        self,
        incident_id: UUID,
        *,
        summary: str,
        actions: list[str],
        expires_at: datetime,
    ) -> ApprovalRequest:
        existing = await self.get_pending_approval(incident_id)
        if existing is not None:
            existing.summary = summary
            existing.actions = actions
            existing.status = "pending"
            existing.expires_at = expires_at.isoformat()
            existing.resolved_at = None
            existing.approved = None
            existing.approved_by = None
            existing.note = ""
            await self.session.commit()
            await self.session.refresh(existing)
            return existing

        row = ApprovalRequest(
            incident_id=incident_id,
            summary=summary,
            actions=actions,
            status="pending",
            expires_at=expires_at.astimezone(UTC).isoformat(),
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def get_pending_approval(self, incident_id: UUID | str) -> ApprovalRequest | None:
        result = await self.session.execute(
            select(ApprovalRequest).where(
                ApprovalRequest.incident_id == incident_id,
                ApprovalRequest.status == "pending",
            )
        )
        return result.scalar_one_or_none()

    async def get_approval(self, incident_id: UUID | str) -> ApprovalRequest | None:
        result = await self.session.execute(
            select(ApprovalRequest).where(ApprovalRequest.incident_id == incident_id)
        )
        return result.scalar_one_or_none()

    async def list_pending_approvals(self) -> list[ApprovalRequest]:
        result = await self.session.execute(
            select(ApprovalRequest)
            .where(ApprovalRequest.status == "pending")
            .order_by(ApprovalRequest.created_at.asc())
        )
        return list(result.scalars().all())

    async def record_approval(
        self,
        incident_id: UUID | str,
        *,
        approved: bool,
        approved_by: str,
        note: str,
    ) -> ApprovalRequest | None:
        row = await self.get_approval(incident_id)
        if row is None:
            return None
        row.status = "approved" if approved else "rejected"
        row.resolved_at = datetime.now(UTC).isoformat()
        row.approved = approved
        row.approved_by = approved_by
        row.note = note
        await self.session.commit()
        await self.session.refresh(row)
        return row
