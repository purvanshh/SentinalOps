from collections.abc import AsyncIterator

from db.session import get_db_session


async def get_db() -> AsyncIterator[object]:
    async for session in get_db_session():
        yield session
