import asyncio
import os
import sys

# Add src path to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../apps/api-server/src")))

from db.session import SessionLocal
from db.models.incident import Incident

async def seed() -> None:
    print("Seeding E2E test database...")
    async with SessionLocal() as session:
        incident = Incident(
            title="Database Connection Spike (E2E Seeded)",
            severity="critical",
            status="open",
            source="prometheus",
            summary="Database pool connections exceeded 90%",
            raw_payload={"triggered": True},
        )
        session.add(incident)
        await session.commit()
    print("Database seeding completed.")

if __name__ == "__main__":
    asyncio.run(seed())
