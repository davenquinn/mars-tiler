from sqlalchemy.exc import InternalError
from pytest import fixture
from sparrow.birdbrain.util import wait_for_database, temp_database
from decimal import Decimal
from pathlib import Path
from dotenv import load_dotenv
from os import environ
from sparrow.utils import get_logger, relative_path
from geoalchemy2.shape import to_shape, WKBElement
from morecantile import Tile
from morecantile.errors import PointOutsideTMSBounds
from pytest import mark, raises, warns
from .database import get_sync_database, initialize_database
from .defs import mars_tms
from .cli import _update_info
from sqlalchemy import event
from sqlalchemy.orm import Session

log = get_logger(__name__)

load_dotenv()


@fixture(scope="session")
def db_conn():
    testing_db = environ.get("MARS_TILER_TEST_DATABASE")
    log.info(f"Database connection: {testing_db}")
    wait_for_database(testing_db)
    with temp_database(testing_db, drop=False) as engine:
        environ["FOOTPRINTS_DATABASE"] = testing_db
        db = get_sync_database(automap=True)
        initialize_database(db)
        yield db


@fixture(scope="class")
def db(db_conn):
    # https://docs.sqlalchemy.org/en/13/orm/session_transaction.html
    # https://gist.github.com/zzzeek/8443477
    connection = db_conn.engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    # start the session in a SAVEPOINT...
    # start the session in a SAVEPOINT...
    session.begin_nested()

    # then each time that SAVEPOINT ends, reopen it
    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(session, transaction):
        if transaction.nested and not transaction._parent.nested:

            # ensure that state is expired the way
            # session.commit() at the top level normally does
            # (optional step)
            session.expire_all()
            session.begin_nested()

    db_conn.session = session
    yield db_conn
    session.close()
    transaction.rollback()
    connection.close()


def test_database(db):
    assert str(db.engine.url) == environ["FOOTPRINTS_DATABASE"]
    res = db.session.execute("SELECT postgis_version()").scalar()
    version = Decimal(res.split(" ")[0])
    assert version >= 3 and version < 4


tile_data = [
    Tile(x=0, y=0, z=0),
    Tile(x=1, y=0, z=1),
    Tile(x=15, y=18, z=5),
    Tile(x=11852, y=4187, z=16),
]

bad_tiles = [
    Tile(x=0, y=0, z=-1),
    Tile(x=1, y=0, z=0),
    Tile(x=2 ** 5 + 2, y=18, z=5),
    Tile(x=11852, y=-100, z=16),
    Tile(x=int(1.55 * 2 ** 17), y=4187, z=17),
]


def get_envelope(db, tile: Tile):
    return to_shape(
        WKBElement(
            db.session.execute(
                "SELECT imagery.tile_envelope(:x,:y,:z)",
                dict(x=tile.x, y=tile.y, z=tile.z),
            ).scalar()
        )
    )


@mark.parametrize("tile", tile_data)
def test_tms_bounds(db, tile):
    res = get_envelope(db, tile)
    assert res.bounds == mars_tms.bounds(tile)


@mark.parametrize("tile", bad_tiles)
def test_bad_tile(db, tile):
    with raises(InternalError):
        get_envelope(db, tile)


fixtures_dir = Path(relative_path(__file__, "..", "test-fixtures"))


class TestDatasets:
    def test_add_mosaics(self, db):
        Mosaic = db.model.imagery_mosaic
        db.session.add(Mosaic(name="hirise_red"))
        db.session.add(Mosaic(name="elevation_model"))
        db.session.commit()

    def test_ingest_datasets(self, db):
        get_sync_database(automap=True)
        hirise = fixtures_dir.glob("*.tif")
        _update_info(hirise, mosaic="hirise_red")

        elevation_models = (fixtures_dir / "elevation-models").glob("*.tif")
        _update_info(elevation_models, mosaic="elevation_model")

        Dataset = db.model.imagery_dataset

        assert db.session.query(Dataset).count() == 4
        assert (
            db.session.query(Dataset)
            .filter(Dataset.mosaic == "elevation_model")
            .count()
            == 3
        )
        assert db.session.query(db.model.imagery_mosaic).count() == 2
