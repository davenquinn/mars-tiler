# 150.5314881731248 -0.211133510973705

from sparrow.utils import relative_path
from pathlib import Path
from .util import get_dataset_info
from pytest import fixture
from shapely.geometry import Point, shape
from morecantile import Tile
from .defs import mars_tms
from .util import MarsCOGReader

fixtures = Path(relative_path(__file__, "..", "test-fixtures"))


@fixture
def hirise_image():
    return fixtures.resolve() / "ESP_037156_1800_RED.byte.tif"


@fixture
def hirise_footprint(hirise_image):
    info = get_dataset_info(hirise_image)
    return shape(info["geometry"])


hirise_center = Point(150.53149, -0.21113)
center_tile = mars_tms.tile(hirise_center.x, hirise_center.y, 12)


def test_dataset_info(hirise_footprint):
    assert hirise_footprint.contains(hirise_center)


def _tile_geom(tile):
    feat = mars_tms.feature(tile)
    return shape(feat["geometry"])


def test_bad_tile(hirise_footprint):
    tile = Tile(5, 11, 11)
    tile_geom = _tile_geom(tile)
    assert not hirise_footprint.intersects(tile_geom)


def test_good_tile(hirise_footprint):
    tile_geom = _tile_geom(center_tile)
    assert hirise_footprint.intersects(tile_geom)


def test_dataset_reader(hirise_image):
    with MarsCOGReader(hirise_image) as reader:
        tile = reader.tile(center_tile.x, center_tile.y, center_tile.z)
