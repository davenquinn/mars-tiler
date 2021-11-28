from dataclasses import dataclass
from typing import Optional, Union, List
import logging

from fastapi import FastAPI, Query
from titiler.core.factory import TilerFactory
from titiler.core.dependencies import DatasetParams, RenderParams, ResamplingName
from titiler.core.errors import DEFAULT_STATUS_CODES, add_exception_handlers
from titiler.mosaic.errors import MOSAIC_STATUS_CODES
from titiler.core.resources.enums import OptionalHeader
from .database import setup_database, get_database
from .async_mosaic import AsyncMosaicFactory, get_datasets
from .util import MarsCOGReader, ElevationReader
from .mosaic import (
    HiRISEMosaicBackend,
    ElevationMosaicBackend,
    mercator_tms,
    elevation_path,
)


def build_path():
    return "/mars-data/hirise-images/hirise-red.mosaic.json"


headers = {OptionalHeader.server_timing, OptionalHeader.x_assets}


app = FastAPI(title="Mars tile server", root_path="/tiles")


def elevation_mosaic_paths(x: int, y: int, z: int):
    # tile = Tile(x, y, z)
    return None


cog = TilerFactory(
    path_dependency=elevation_path, reader=ElevationReader, optional_headers=headers
)


def HiRISEParams(
    image_id: str = Query(..., description="HiRISE image ID"), image_type: str = "RED"
) -> str:
    """Create dataset path from args"""
    return f"/mars-data/hirise-images/{image_id}_{image_type}.tif"


@dataclass
class HiRISEImageParams(DatasetParams):
    """Low level WarpedVRT Optional parameters."""

    # nodata: Optional[Union[str, int, float]] = Query(
    #     0, title="Nodata value", description="Overwrite internal Nodata value"
    # )


@dataclass
class HiRISERenderParams(RenderParams):
    rescale: Optional[List[str]] = Query(
        ["100,1200"],
        title="Min/Max data Rescaling",
        description="comma (',') delimited Min,Max bounds. Can set multiple time for multiple bands.",
    )


def MosaicParams(mosaic: str = Query(..., description="Mosaic ID")) -> str:
    """Mosaic ID"""
    return mosaic


hirise_mosaic = AsyncMosaicFactory(
    reader=HiRISEMosaicBackend,
    path_dependency=MosaicParams,
    optional_headers=headers,
    dataset_dependency=HiRISEImageParams,
    render_dependency=HiRISERenderParams,
)

hirise_cog = TilerFactory(
    reader=MarsCOGReader,
    path_dependency=HiRISEParams,
    dataset_dependency=HiRISEImageParams,
    render_dependency=HiRISERenderParams,
)
app.include_router(hirise_cog.router, tags=["HiRISE images"], prefix="/hirise")


@dataclass
class ElevationMosaicParams(DatasetParams):
    resampling_method: ResamplingName = Query(
        ResamplingName.bilinear,  # type: ignore
        alias="resampling",
        description="Resampling method.",
    )


# This is the main dataset
elevation_mosaic = AsyncMosaicFactory(
    path_dependency=lambda: "elevation_model",
    dataset_dependency=ElevationMosaicParams,
    reader=ElevationMosaicBackend,
    optional_headers=headers,
)
app.include_router(
    elevation_mosaic.router, tags=["Elevation Mosaic"], prefix="/elevation-mosaic"
)

app.include_router(
    hirise_mosaic.router, tags=["Imagery Mosaic"], prefix="/mosaic/{mosaic}"
)
app.include_router(cog.router, tags=["Global DEM"], prefix="/elevation-global")


@app.get("/datasets/{mosaic}")
async def dataset(mosaic: str, lon: float = None, lat: float = None, zoom: int = 4):
    tile = mercator_tms.tile(lon, lat, zoom)
    xy_bounds = mercator_tms.xy_bounds(tile)
    bounds = mercator_tms.bounds(tile)

    datasets = await get_datasets(tile, mosaic)

    return {
        "mercator_bounds": xy_bounds,
        "latlng_bounds": bounds,
        "tile": tile,
        "datasets": [d for d in datasets],
    }


add_exception_handlers(app, DEFAULT_STATUS_CODES)
add_exception_handlers(app, MOSAIC_STATUS_CODES)


@app.on_event("startup")
async def startup_event():
    await setup_database()
    logger = logging.getLogger("mars_tile_server")
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)


@app.on_event("shutdown")
async def shutdown_event():
    db = await get_database()
    await db.disconnect()
