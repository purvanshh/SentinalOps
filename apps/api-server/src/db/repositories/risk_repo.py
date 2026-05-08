from sqlalchemy import select

from db.models import RemediationHistory
from db.repositories import BaseRepository


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
