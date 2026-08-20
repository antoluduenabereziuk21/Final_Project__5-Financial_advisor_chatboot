from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.settings import settings
from app.db.models import Base


engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
)
session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def init_database() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def close_database() -> None:
    await engine.dispose()