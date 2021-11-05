from os import environ
from sparrow.birdbrain import Database

dbname = environ.get("FOOTPRINTS_DATABASE")
db = Database(dbname)
