from os import environ
from databases import Database

# Create a table.
database = Database(environ.get("FOOTPRINTS_DATABASE"))


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
