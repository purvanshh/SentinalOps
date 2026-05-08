import asyncio

from db.session import initialize_database


def main() -> None:
    asyncio.run(initialize_database())


if __name__ == "__main__":
    main()
