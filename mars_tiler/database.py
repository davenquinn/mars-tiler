from os import environ
from sparrow.birdbrain import Database as SyncDatabase
from sparrow.utils import relative_path
from psycopg_pool import ConnectionPool
from contextvars import ContextVar


from fastapi import FastAPI


def setup_database() -> None:
    """Connect to Database."""
    dbpool = ConnectionPool(
        conninfo=environ.get("FOOTPRINTS_DATABASE"),
        min_size=1,  # The minimum number of connection the pool will hold
        max_size=10,  # The maximum number of connections the pool will hold
        max_waiting=50000,  # Maximum number of requests that can be queued to the pool
        max_idle=300,  # Maximum time, in seconds, that a connection can stay unused in the pool before being closed, and the pool shrunk.
        num_workers=3,  # Number of background worker threads used to maintain the pool state
        kwargs={
            "options": "-c search_path=tile_cache,public -c application_name=tile_cache"
        },
    )
    db_ctx.set(dbpool)


db_ctx = ContextVar("db_ctx", default=None)
setup_database()


def get_database():
    return db_ctx.get()


async def teardown_database() -> None:
    """Close Pool."""
    dbpool = db_ctx.get()
    if dbpool is not None:
        dbpool.close()
        await dbpool.wait_closed()
        db_ctx.set(None)


db = None


def get_sync_database():
    global db
    if db is None:
        db = SyncDatabase(environ.get("FOOTPRINTS_DATABASE"))
    if getattr(db, "mapper") is None:
        db.automap()
        # We seem to have to remap public for changes to take hold...
        # db.mapper.reflect_schema("public")
        db.mapper.reflect_schema("imagery")
        db.mapper.reflect_schema("public")
        # OK, wait, we just have to map the public schema last...
    return db


stmt_cache = {}


def prepared_statement(id):
    cached = stmt_cache.get(id)
    if cached is None:
        stmt_cache[id] = open(relative_path(__file__, "sql", f"{id}.sql"), "r").read()
    return stmt_cache[id]
