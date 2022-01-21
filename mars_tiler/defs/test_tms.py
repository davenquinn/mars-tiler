from morecantile.models import TileMatrixSet, Tile
from pydantic import BaseModel
from pytest import mark
import rasterio
from .crs import mars_radius
from . import MARS2000_SPHERE, MARS_MERCATOR, mercator_tms, mars_tms


class PositionTest(BaseModel):
    lon: float
    lat: float
    tile: Tile


positions = [
    PositionTest(lon=149.936, lat=-3.752, tile=Tile(7507, 4181, 13)),
    PositionTest(lon=20, lat=-80, tile=Tile(18204, 29089, 15)),
    PositionTest(lon=149.9, lat=-3.8, tile=Tile(3753, 2091, 12)),
]


def test_mars_projection():
    assert (
        MARS_MERCATOR.ellipsoid.semi_major_metre
        == MARS2000_SPHERE.ellipsoid.semi_major_metre
    )


def _test_tms(tms: TileMatrixSet, pos: PositionTest):
    tile = tms.tile(pos.lon, pos.lat, pos.tile.z)
    assert tile.x == pos.tile.x
    assert tile.y == pos.tile.y


@mark.parametrize("pos", positions)
def test_positions(pos):
    """Should have correct positions with standard web mercator"""
    _test_tms(mercator_tms, pos)


@mark.parametrize("pos", positions)
def test_mars_positions(pos):
    """Returned positions should be the same for Earth and Mars Mercator TMS"""
    _test_tms(mars_tms, pos)


dataset_wkt = """PROJCRS["EQUIRECTANGULAR MARS",
BASEGEOGCRS["GCS_MARS",
    DATUM["D_MARS",
        ELLIPSOID["MARS_localRadius",3396190,0,
            LENGTHUNIT["metre",1,
                ID["EPSG",9001]]]],
    PRIMEM["Reference_Meridian",0,
        ANGLEUNIT["degree",0.0174532925199433,
            ID["EPSG",9122]]]],
CONVERSION["Equidistant Cylindrical",
    METHOD["Equidistant Cylindrical",
        ID["EPSG",1028]],
    PARAMETER["Latitude of 1st standard parallel",0,
        ANGLEUNIT["degree",0.0174532925199433],
        ID["EPSG",8823]],
    PARAMETER["Longitude of natural origin",149.9,
        ANGLEUNIT["degree",0.0174532925199433],
        ID["EPSG",8802]],
    PARAMETER["False easting",0,
        LENGTHUNIT["metre",1],
        ID["EPSG",8806]],
    PARAMETER["False northing",0,
        LENGTHUNIT["metre",1],
        ID["EPSG",8807]]],
CS[Cartesian,2],
    AXIS["easting",east,
        ORDER[1],
        LENGTHUNIT["metre",1,
            ID["EPSG",9001]]],
    AXIS["northing",north,
        ORDER[2],
        LENGTHUNIT["metre",1,
            ID["EPSG",9001]]]]
"""


def test_crs_transformation_speed():
    for i in range(5000):
        crs = MARS2000_SPHERE.to_wkt()
        rasterio.crs.CRS.from_wkt(crs)


def test_crs_transformation_speed_wkt():
    for i in range(5000):
        rasterio.crs.CRS.from_wkt(dataset_wkt)


def test_crs_transformations_internal():
    for i in range(5000):
        crs = MARS2000_SPHERE.to_wkt()
        rcrs = rasterio.crs.CRS.from_wkt(crs)
        rcrs.to_epsg()
        rcrs.to_authority()
