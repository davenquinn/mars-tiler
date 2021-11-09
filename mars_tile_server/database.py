from os import environ
from contextvars import ContextVar
from sqlalchemy import create_engine
from asyncio import run

db_ctx = ContextVar("database", default=None)


def setup_database():
    try:
        engine = create_engine(environ.get("FOOTPRINTS_DATABASE"))
        conn = engine.connect()
        db_ctx.set(conn)
        return conn
    except AttributeError:
        return None


def get_database():
    conn = db_ctx.get()
    if conn is None:
        return setup_database()
    return conn
