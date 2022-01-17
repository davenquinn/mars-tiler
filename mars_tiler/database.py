from os import environ
from databases import Database
from sparrow.birdbrain import Database as SyncDatabase
from sparrow.utils import relative_path

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


# Create a table.
database = None
try:
    database = Database(environ.get("FOOTPRINTS_DATABASE"))
except TypeError:
    pass


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


stmt_cache = {}


def prepared_statement(id):
    cached = stmt_cache.get(id)
    if cached is None:
        stmt_cache[id] = open(relative_path(__file__, "sql", f"{id}.sql"), "r").read()
    return stmt_cache[id]
