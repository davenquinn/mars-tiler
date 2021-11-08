from morecantile.models import TileMatrixSet, Tile
from pydantic import BaseModel
from pytest import mark
from .crs import mars_radius
from . import MARS2000_SPHERE, MARS_MERCATOR, mercator_tms, mars_tms


class PositionTest(BaseModel):
    lon: float
    lat: float
    tile: Tile


positions = [
    PositionTest(lon=149.936, lat=-3.752, tile=Tile(7507, 4181, 13)),
    PositionTest(lon=20, lat=-80, tile=Tile(18204, 29089, 15)),
]


def test_mars_projection():
    assert MARS2000_SPHERE.to_dict().get("R") == mars_radius
    assert MARS_MERCATOR.to_dict().get("R") == mars_radius


def _test_tms(tms: TileMatrixSet, pos: PositionTest):
    tile = tms.tile(pos.lon, pos.lat, pos.tile.z)
    assert tile.x == pos.tile.x
    assert tile.y == pos.tile.y


@mark.parametrize("pos", positions)
def test_positions(pos):
    """Should have correct positions on Earth"""
    _test_tms(mercator_tms, pos)


@mark.parametrize("pos", positions)
def test_mars_positions(pos):
    """Returned positions should be the same for Earth and Mars Mercator TMS"""
    _test_tms(mars_tms, pos)
