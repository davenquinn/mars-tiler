from os import environ
from sparrow.birdbrain import Database

db = None


def get_database(setup=False):
    if db is None:
        return None
    if setup and getattr(db, "mapper") is None:
        db.automap()
        # We seem to have to remap public for changes to take hold...
        db.mapper.reflect_schema("public")
        db.mapper.reflect_schema("imagery")
        db.mapper.reflect_schema("public")
    return db


try:
    db = Database(environ.get("FOOTPRINTS_DATABASE"))
    get_database(setup=True)
except AttributeError:
    pass
