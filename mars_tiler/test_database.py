from pytest import fixture
from sparrow.birdbrain.util import wait_for_database, temp_database
from dotenv import load_dotenv
from os import environ
from sparrow.utils import get_logger
from .database import get_sync_database, initialize_database

log = get_logger(__name__)

load_dotenv()


@fixture(scope="session")
def db():
    testing_db = environ.get("MARS_TILER_TEST_DATABASE")
    log.info(f"Database connection: {testing_db}")
    wait_for_database(testing_db)
    with temp_database(testing_db, drop=False) as engine:
        environ["FOOTPRINTS_DATABASE"] = testing_db
        db = get_sync_database()
        initialize_database(db)
        yield db


def test_database(db):
    assert str(db.engine.url) == environ["FOOTPRINTS_DATABASE"]
