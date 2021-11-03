from os import environ
from birdbrain import Database

dbname = environ.get("FOOTPRINTS_DATABASE")
db = Database(dbname)
