from sqlalchemy import select

from db.models import Postmortem, PreventionItem
from db.repositories import BaseRepository


class PostmortemRepository(BaseRepository):
    async def create_postmortem(
        self,
        *,
        incident_id,
        title: str,
        content: str,
        version: int = 1,
    ) -> Postmortem:
        row = Postmortem(
            incident_id=incident_id,
            title=title,
            content=content,
            version=version,
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def list_postmortems(self, incident_id) -> list[Postmortem]:
        result = await self.session.execute(
            select(Postmortem).where(Postmortem.incident_id == incident_id).order_by(Postmortem.version.asc())
        )
        return list(result.scalars().all())

    async def list_prevention_items(self) -> list[PreventionItem]:
        result = await self.session.execute(select(PreventionItem).order_by(PreventionItem.created_at.asc()))
        return list(result.scalars().all())

    async def create_prevention_items(self, items: list[dict]) -> list[PreventionItem]:
        rows: list[PreventionItem] = []
        for item in items:
            row = PreventionItem(**item)
            self.session.add(row)
            rows.append(row)
        await self.session.commit()
        for row in rows:
            await self.session.refresh(row)
        return rows
