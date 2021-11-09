from dataclasses import dataclass
from typing import Optional, Union, List
import logging

from fastapi import FastAPI, Query
from cogeo_mosaic.backends import MosaicBackend
from titiler.mosaic.factory import MosaicTilerFactory
from titiler.mosaic.errors import MOSAIC_STATUS_CODES
from titiler.core.factory import TilerFactory
from titiler.core.dependencies import DatasetParams, RenderParams
from titiler.core.errors import DEFAULT_STATUS_CODES, add_exception_handlers
from titiler.core.resources.enums import OptionalHeader
from .util import MarsCOGReader, ElevationReader
from .mosaic import (
    MarsMosaicBackend,
    ElevationMosaicBackend,
    get_datasets,
    mercator_tms,
    elevation_path,
)


def build_path():
    return "/mars-data/hirise-images/hirise-red.mosaic.json"


headers = {OptionalHeader.server_timing, OptionalHeader.x_assets}


hirise_mosaic = MosaicTilerFactory(
    reader=MarsMosaicBackend, path_dependency=build_path, optional_headers=headers
)

app = FastAPI(title="Mars tile server")


def elevation_mosaic_paths(x: int, y: int, z: int):
    # tile = Tile(x, y, z)
    return None


cog = TilerFactory(
    path_dependency=elevation_path, reader=ElevationReader, optional_headers=headers
)

elevation_mosaic = MosaicTilerFactory(
    path_dependency=elevation_mosaic_paths,
    reader=ElevationMosaicBackend,
    optional_headers=headers,
)

app.include_router(
    elevation_mosaic.router, tags=["Elevation Mosaic"], prefix="/elevation-mosaic"
)
app.include_router(
    hirise_mosaic.router, tags=["HiRISE Mosaic"], prefix="/hirise-mosaic"
)
app.include_router(cog.router, tags=["Global DEM"], prefix="/elevation-global")


def HiRISEParams(
    image_id: str = Query(..., description="HiRISE image ID"), image_type: str = "RED"
) -> str:
    """Create dataset path from args"""
    return f"/mars-data/hirise-images/{image_id}_{image_type}.tif"


@dataclass
class HiRISEImageParams(DatasetParams):
    """Low level WarpedVRT Optional parameters."""

    nodata: Optional[Union[str, int, float]] = Query(
        0, title="Nodata value", description="Overwrite internal Nodata value"
    )


@dataclass
class HiRISERenderParams(RenderParams):
    rescale: Optional[List[str]] = Query(
        ["100,1200"],
        title="Min/Max data Rescaling",
        description="comma (',') delimited Min,Max bounds. Can set multiple time for multiple bands.",
    )


hirise_cog = TilerFactory(
    reader=MarsCOGReader,
    path_dependency=HiRISEParams,
    dataset_dependency=HiRISEImageParams,
    render_dependency=HiRISERenderParams,
)
app.include_router(hirise_cog.router, tags=["HiRISE images"], prefix="/hirise")


@app.get("/datasets/{mosaic}")
async def dataset(mosaic: str, lon: float = None, lat: float = None, zoom: int = 4):
    tile = mercator_tms.tile(lon, lat, zoom)
    xy_bounds = mercator_tms.xy_bounds(tile)
    bounds = mercator_tms.bounds(tile)

    datasets = get_datasets(tile, mosaic)

    return {
        "mercator_bounds": xy_bounds,
        "latlng_bounds": bounds,
        "tile": tile,
        "datasets": [d.path for d in datasets],
    }


add_exception_handlers(app, DEFAULT_STATUS_CODES)
add_exception_handlers(app, MOSAIC_STATUS_CODES)


@app.on_event("startup")
async def startup_event():
    logger = logging.getLogger("mars_tile_server")
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)
