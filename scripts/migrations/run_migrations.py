import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API_SRC = ROOT / "apps" / "api-server" / "src"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))


def main() -> None:
    from db.session import initialize_database

    asyncio.run(initialize_database())


if __name__ == "__main__":
    main()
