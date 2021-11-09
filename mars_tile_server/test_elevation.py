from pathlib import Path
from typing import List

from morecantile import Tile
from pydantic import BaseModel
from pytest import fixture
from rio_tiler.models import ImageData
from rio_rgbify.encoders import data_to_rgb
from shapely.geometry import Polygon

from .defs.test_tms import positions
from .mosaic import MarsMosaicBackend, ElevationMosaicBackend
from ._test_utils import dataset_footprint, fixtures, _tile_geom


class Dataset(BaseModel):
    class Config:
        arbitrary_types_allowed = True

    path: Path
    footprint: Polygon


@fixture(scope="module")
def elevation_models():
    paths = (fixtures.resolve() / "elevation-models").glob("*.tif")
    return [Dataset(path=d, footprint=dataset_footprint(d)) for d in paths]


class MarsTestMosaicBackend(MarsMosaicBackend):
    datasets: List[Dataset]

    def __init__(self, datasets, *args, **kwargs):
        self.datasets = datasets
        super().__init__(self, None, *args, **kwargs)

    def _get_assets(self, tile: Tile) -> List[str]:
        tile_feature = _tile_geom(tile)
        return [
            str(d.path) for d in self.datasets if tile_feature.intersects(d.footprint)
        ]


class ElevationTestMosaicBackend(MarsTestMosaicBackend, ElevationMosaicBackend):
    ...


@fixture(scope="module")
def mosaic_backend(elevation_models):
    return MarsTestMosaicBackend(elevation_models)


@fixture(scope="module")
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
