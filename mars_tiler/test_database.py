from pytest import fixture
from sparrow.birdbrain.util import wait_for_database, temp_database
from decimal import Decimal
from dotenv import load_dotenv
from os import environ
from sparrow.utils import get_logger
from geoalchemy2.shape import to_shape, WKBElement
from morecantile import Tile
from pytest import mark
from .database import get_sync_database, initialize_database
from .defs import mars_tms

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
    res = db.session.execute("SELECT postgis_version()").scalar()
    version = Decimal(res.split(" ")[0])
    assert version >= 3 and version < 4


tile_data = [
    Tile(x=0, y=0, z=0),
    Tile(x=1, y=0, z=1),
    Tile(x=15, y=18, z=5),
    Tile(x=11852, y=4187, z=16),
]


@mark.parametrize("tile", tile_data)
def test_tms_bounds(db, tile):
    res = to_shape(
        WKBElement(
            db.session.execute(
                "SELECT imagery.tile_envelope(:x,:y,:z)",
                dict(x=tile.x, y=tile.y, z=tile.z),
            ).scalar()
        )
    )
    assert res.bounds == mars_tms.bounds(tile)
