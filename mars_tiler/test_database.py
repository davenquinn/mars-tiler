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
from pytest import mark, raises

from .database import get_sync_database, initialize_database
from .defs import mars_tms
from .cli import _update_info

log = get_logger(__name__)

load_dotenv()


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


def geometry_scalar(query):
    return to_shape(WKBElement(query.scalar()))


def get_envelope(db, tile: Tile):
    return geometry_scalar(
        db.session.execute(
            "SELECT imagery.tile_envelope(:x,:y,:z)",
            dict(x=tile.x, y=tile.y, z=tile.z),
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

    def _test_tile_bounds(self, db, name):
        res = db.session.execute(
            "SELECT (imagery.parent_tile(footprint)).* FROM imagery.dataset WHERE name = :name",
            dict(name=name),
        ).one()

        tile_footprint = get_envelope(db, res)
        assert tile_footprint.bounds == mars_tms.bounds(res)

        dataset_footprint = geometry_scalar(
            db.session.execute(
                "SELECT footprint FROM imagery.dataset WHERE name = :name",
                dict(name=name),
            )
        )

        assert tile_footprint.contains(dataset_footprint)

    def test_tile_bounds(self, db):
        # We are currently having trouble parameterizing these as separate tests
        res = db.session.query(db.model.imagery_dataset.name).all()
        for row in res:
            self._test_tile_bounds(db, row.name)
