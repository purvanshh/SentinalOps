from collections.abc import AsyncIterator

from db.session import get_db_session
from sqlalchemy.ext.asyncio import AsyncSession


async def get_session() -> AsyncIterator[AsyncSession]:
    async for session in get_db_session():
        yield session
