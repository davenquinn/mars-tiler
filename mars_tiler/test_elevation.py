from pathlib import Path
from typing import List

from morecantile import Tile
from pydantic import BaseModel
from pytest import mark, fixture
from rio_tiler.models import ImageData
from shapely.geometry import Polygon

from .defs.test_tms import positions
from .mosaic import MarsMosaicBackend, ElevationMosaicBackend
from ._test_utils import dataset_footprint, fixtures, _tile_geom
from .mosaic.base import MosaicAsset


class DatasetTestData(BaseModel):
    class Config:
        arbitrary_types_allowed = True

    path: Path
    footprint: Polygon


@fixture(scope="module")
def elevation_models():
    paths = (fixtures.resolve() / "elevation-models").glob("*.tif")
    return [DatasetTestData(path=d, footprint=dataset_footprint(d)) for d in paths]


class MarsTestMosaicBackend(MarsMosaicBackend):
    datasets: List[DatasetTestData]

    def __init__(self, datasets, *args, **kwargs):
        self.datasets = datasets
        super().__init__(self, None, *args, **kwargs)

    def get_assets(self, x: int, y: int, z: int) -> List[MosaicAsset]:
        tile_feature = _tile_geom(Tile(x, y, z))
        return [
            MosaicAsset(
                path=str(d.path),
                mosaic="elevation",
                rescale_range=None,
                minzoom=0,
                maxzoom=18,
                overscaled=False,
            )
            for d in self.datasets
            if tile_feature.intersects(d.footprint)
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
    test_tile = Tile(234, 130, 8)
    assets = elevation_backend.get_assets(test_tile.x, test_tile.y, test_tile.z)
    assert len(assets) == 3

    tile_data, tile_assets = elevation_backend.tile(
        test_tile.x, test_tile.y, test_tile.z
    )
    assert len(tile_assets) == 3
    assert isinstance(tile_data, ImageData)
    assert tile_data.data.shape == (3, 256, 256)
