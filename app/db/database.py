import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

# In production DATABASE_URL must be set explicitly (populated by Coolify).
# There is no hardcoded production fallback: fail closed instead.
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    if os.getenv("VNP_ENV", "development").lower() in ("production", "prod"):
        raise RuntimeError(
            "Refusing production startup: DATABASE_URL is not configured."
        )
    DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/veklom"

if os.getenv("VNP_DB_POOL") == "null":
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(DATABASE_URL, echo=False, poolclass=NullPool)
else:
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        pool_size=10,
        max_overflow=20
    )

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()

async def get_db():
    """Dependency injection for database sessions"""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
