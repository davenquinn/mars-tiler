from pathlib import Path
from typing import List

from morecantile import Tile
from pydantic import BaseModel
from pytest import fixture
from rio_tiler.models import ImageData
from rio_rgbify.encoders import data_to_rgb
from shapely.geometry import Polygon

from .defs.test_tms import positions
from .mosaic import MarsMosaicBackend
from ._test_utils import dataset_footprint, fixtures, _tile_geom


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


@fixture
def mosaic_backend(elevation_models):
    return MarsTestMosaicBackend(elevation_models)


@fixture
def elevation_backend(elevation_models):
    return ElevationTestMosaicBackend(elevation_models)


def test_basic_tiler(mosaic_backend):
    test_tile = positions[0].tile
    tile_data, assets = mosaic_backend.tile(test_tile.x, test_tile.y, test_tile.z)
    assert tile_data.data.shape == (1, 256, 256)


def test_elevation_tiler(elevation_backend):
    test_tile = positions[0].tile
    tile_data, assets = elevation_backend.tile(test_tile.x, test_tile.y, test_tile.z)
    assert len(assets) == 2
    assert isinstance(tile_data, ImageData)
    assert tile_data.data.shape == (3, 256, 256)
