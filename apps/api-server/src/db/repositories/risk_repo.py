from db.models import RemediationHistory
from db.repositories import BaseRepository
from sqlalchemy import select


class RiskRepository(BaseRepository):
    async def list_remediation_history(self) -> list[RemediationHistory]:
        result = await self.session.execute(select(RemediationHistory))
        return list(result.scalars().all())

    async def seed_remediation_history(self, items: list[dict]) -> list[RemediationHistory]:
        existing = await self.list_remediation_history()
        if existing:
            return existing
        rows: list[RemediationHistory] = []
        for item in items:
            row = RemediationHistory(**item)
            self.session.add(row)
            rows.append(row)
        await self.session.commit()
        for row in rows:
            await self.session.refresh(row)
        return rows

    async def record_remediation_outcome(
        self,
        *,
        action_name: str,
        category: str,
        success: bool,
        execution_time_seconds: float,
        severity_on_failure: float,
    ) -> RemediationHistory:
        row = RemediationHistory(
            action_name=action_name,
            category=category,
            success=success,
            execution_time_seconds=execution_time_seconds,
            severity_on_failure=severity_on_failure,
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row
