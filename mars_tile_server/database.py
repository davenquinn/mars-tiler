from os import environ
from sparrow.birdbrain import Database

dbname = environ.get("FOOTPRINTS_DATABASE")
_db = Database(dbname, echo_sql=False)


def get_database():
    if getattr(_db, "mapper") is None:
        _db.automap()
        # We seem to have to remap public for changes to take hold...
        _db.mapper.reflect_schema("public")
        _db.mapper.reflect_schema("imagery")
        _db.mapper.reflect_schema("public")

    return _db
