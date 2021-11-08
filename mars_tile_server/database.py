from os import environ
from sparrow.birdbrain import Database

db = None
try:
    db = Database(environ.get("FOOTPRINTS_DATABASE"))
except AttributeError:
    pass


def get_database():
    if db is None:
        return None
    if getattr(db, "mapper") is None:
        db.automap()
        # We seem to have to remap public for changes to take hold...
        db.mapper.reflect_schema("public")
        db.mapper.reflect_schema("imagery")
        db.mapper.reflect_schema("public")
    return db
