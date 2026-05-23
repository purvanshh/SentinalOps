import asyncio
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
API_SRC = ROOT / "apps" / "api-server" / "src"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))


async def seed() -> None:
    from core.config import get_settings
    from retrieval.embeddings.embedding_client import EmbeddingClient

    settings = get_settings()
    fixtures_path = ROOT / "configs" / "development" / "past_incidents.json"
    incidents = json.loads(fixtures_path.read_text())
    embedder = EmbeddingClient()

    async with httpx.AsyncClient(base_url=settings.qdrant_url, timeout=10.0) as client:
        await client.put(
            "/collections/past_incidents",
            json={
                "vectors": {
                    "size": embedder.dimensions,
                    "distance": "Cosine",
                }
            },
        )
        points = []
        for index, incident in enumerate(incidents, start=1):
            text = f"{incident['title']}\n{incident['summary']}"
            points.append(
                {
                    "id": index,
                    "vector": embedder.embed_text(text),
                    "payload": incident,
                }
            )
        await client.put(
            "/collections/past_incidents/points",
            json={"points": points},
        )


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
