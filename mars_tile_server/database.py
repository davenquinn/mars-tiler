from os import environ
from sparrow.birdbrain import Database
from contextvars import ContextVar

database_ctx: ContextVar[Database] = ContextVar("database", default=None)


def get_database():
    db = database_ctx.get()
    if db is None:
        dbname = environ.get("FOOTPRINTS_DATABASE")
        db = Database(dbname, echo_sql=False)
        database_ctx.set(db)
    if getattr(db, "mapper") is None:
        db.automap()
        # We seem to have to remap public for changes to take hold...
        db.mapper.reflect_schema("public")
        db.mapper.reflect_schema("imagery")
        db.mapper.reflect_schema("public")

    return db
