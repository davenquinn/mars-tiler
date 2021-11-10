from os import environ
from contextvars import ContextVar
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from contextlib import asynccontextmanager
from databases import Database

# Create a table.

# db_ctx = ContextVar("database", default=None)
database = Database(environ.get("FOOTPRINTS_DATABASE"))


async def setup_database():
    try:
        await database.connect()
        return database
    except AttributeError:
        return None


async def get_database():
    if database is None:
        return await setup_database()
    return database
