from os import environ
from sparrow.birdbrain import Database
from contextvars import ContextVar

db_ctx = ContextVar("database", default=None)

try:
    db_ctx.set(Database(environ.get("FOOTPRINTS_DATABASE")).engine.connect())
except AttributeError:
    pass


def get_database():
    conn = db_ctx.get()
    if conn is None:
        return None
    return conn
