import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

# The Coolify standalone PostgreSQL connection
# In production this comes from environment variables populated by Coolify
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@llwfyzhnft87bz6brddiax1z:5432/veklom")

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
