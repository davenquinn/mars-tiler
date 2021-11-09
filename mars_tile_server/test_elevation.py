from sparrow.utils import relative_path
from pathlib import Path
from .util import ElevationReader, get_dataset_info
from pytest import fixture, raises
from shapely.geometry import Point, shape, Polygon
from rio_tiler.models import ImageData
from rio_tiler.errors import TileOutsideBounds
from rio_rgbify.encoders import data_to_rgb
from morecantile import Tile
from typing import List
from .defs import mars_tms
from .util import MarsCOGReader
from ._test_utils import dataset_footprint, fixtures, _tile_geom
from .defs.test_tms import positions
from .mosaic import ElevationMosaicBackend, MarsMosaicBackend, ElevationReader
from pydantic import BaseModel


class Dataset(BaseModel):
    class Config:
        arbitrary_types_allowed = True

    path: Path
    footprint: Polygon


@fixture
def elevation_models():
    return list((fixtures.resolve() / "elevation-models").glob("*.tif"))


class MarsTestMosaicBackend(MarsMosaicBackend):
    datasets: List[Dataset]

    def __init__(self, datasets, *args, **kwargs):
        self.datasets = [
            Dataset(path=d, footprint=dataset_footprint(d)) for d in datasets
        ]
        super().__init__(None, *args, **kwargs)

    def get_assets(self, x: int, y: int, z: int) -> List[str]:
        tile = _tile_geom(Tile(x, y, z))
        return [str(d.path) for d in self.datasets if tile.intersects(d.footprint)]


class ElevationTestMosaicBackend(MarsTestMosaicBackend):
    def tile(self, *args, **kwargs):
        im, assets = super().tile(*args, **kwargs)
        im.data = data_to_rgb(im.data[0], -10000, 0.1)
        return (im, assets)


def test_basic_tiler(elevation_models):
    test_tile = positions[0].tile
    backend = MarsTestMosaicBackend(elevation_models)
    tile_data = backend.tile(test_tile.x, test_tile.y, test_tile.z)
    assert True


def test_elevation_tiler(elevation_models):
    test_tile = positions[0].tile
    backend = ElevationTestMosaicBackend(elevation_models)
    tile_data = backend.tile(test_tile.x, test_tile.y, test_tile.z)
