# 150.5314881731248 -0.211133510973705

from sparrow.utils import relative_path
from pathlib import Path
from pytest import fixture, raises
from shapely.geometry import Point, shape
from rio_tiler.errors import TileOutsideBounds
from morecantile import Tile
from .defs import mars_tms
from .util import MarsCOGReader
from ._test_utils import fixtures, dataset_footprint, _tile_geom


@fixture
def hirise_image():
    return fixtures / "ESP_037156_1800_RED.byte.tif"


@fixture
def hirise_footprint(hirise_image):
    return dataset_footprint(hirise_image)


@fixture
def hirise_reader(hirise_image):
    with MarsCOGReader(hirise_image) as reader:
        yield reader


hirise_center = Point(150.53149, -0.21113)
center_tile = mars_tms.tile(hirise_center.x, hirise_center.y, 12)
random_tile = Tile(5, 11, 11)


def test_dataset_info(hirise_footprint):
    assert hirise_footprint.contains(hirise_center)


def test_bad_tile(hirise_footprint):
    tile_geom = _tile_geom(random_tile)
    assert not hirise_footprint.intersects(tile_geom)


def test_good_tile(hirise_footprint):
    tile_geom = _tile_geom(center_tile)
    assert hirise_footprint.intersects(tile_geom)


def test_dataset_reader(hirise_reader):
    tile = hirise_reader.tile(center_tile.x, center_tile.y, center_tile.z)
    assert tile.width == 256


def test_read_random_tile(hirise_reader):
    with raises(TileOutsideBounds):
        hirise_reader.tile(random_tile.x, random_tile.y, random_tile.z)
