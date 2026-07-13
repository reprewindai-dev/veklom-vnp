import asyncio
import os

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:55432/veklom",
)
os.environ.setdefault("VNP_DB_POOL", "null")


def _database_reachable() -> bool:
    import asyncpg

    async def _try():
        url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
        conn = await asyncpg.connect(url, timeout=3)
        await conn.close()

    try:
        asyncio.new_event_loop().run_until_complete(_try())
        return True
    except Exception:
        return False


requires_database = pytest.mark.skipif(
    not _database_reachable(), reason="test database not reachable"
)
