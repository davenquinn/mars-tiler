import logging
from pytest import fixture
from sparrow.birdbrain.util import wait_for_database, temp_database
from dotenv import load_dotenv
from os import environ
from sparrow.utils import get_logger, relative_path
from pathlib import Path

from mars_tiler.database import get_sync_database, initialize_database

disable_loggers = []  # "rasterio"]
log = get_logger(__name__)

load_dotenv()


def pytest_configure():
    for logger_name in disable_loggers:
        logger = logging.getLogger(logger_name)
        logger.disabled = True


@fixture(scope="session")
def db_conn():
    testing_db = environ.get("MARS_TILER_TEST_DATABASE")
    log.info(f"Database connection: {testing_db}")
    wait_for_database(testing_db)
    with temp_database(testing_db, drop=False, ensure_empty=True) as engine:
        environ["FOOTPRINTS_DATABASE"] = testing_db
        db = get_sync_database(automap=False)
        initialize_database(db)
        db = get_sync_database(automap=True)
        yield db


@fixture()
def db(db_conn):
    with db_conn.session_scope():
        yield db_conn


@fixture(scope="session")
def fixtures_dir():
    return Path(relative_path(__file__, "test-fixtures"))
