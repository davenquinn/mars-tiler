from os import environ
from contextvars import ContextVar
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from contextlib import asynccontextmanager

db_ctx = ContextVar("database", default=None)


def setup_database():
    try:
        engine = create_async_engine(
            environ.get("FOOTPRINTS_DATABASE").replace(
                "postgresql://", "postgresql+asyncpg://"
            )
        )
        db_ctx.set(engine)
        return engine
    except AttributeError:
        return None


@asynccontextmanager
async def get_database() -> AsyncSession:
    engine = db_ctx.get()
    if engine is None:
        engine = setup_database()
    async with engine.connect() as conn:
        yield conn
    await engine.dispose()
