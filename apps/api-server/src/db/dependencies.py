from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db_session


async def get_session() -> AsyncIterator[AsyncSession]:
    async for session in get_db_session():
        yield session
