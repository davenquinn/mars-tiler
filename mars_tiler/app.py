from dataclasses import dataclass
from typing import Optional, Union, List
import logging
import os

from fastapi import FastAPI, Query
from titiler.core.factory import TilerFactory
from titiler.core.dependencies import DatasetParams, PostProcessParams, ResamplingName
from titiler.core.errors import DEFAULT_STATUS_CODES, add_exception_handlers
from titiler.mosaic.errors import MOSAIC_STATUS_CODES
from titiler.core.resources.enums import OptionalHeader
from .database import setup_database, get_sync_database
from .routes import MosaicRouteFactory, get_datasets
from .util import MarsCOGReader, dataset_path
from .mosaic import (
    MarsMosaicBackend,
    ElevationMosaicBackend,
    mercator_tms,
)


def build_path(*args):
    return dataset_path("/hirise-images/hirise-red.mosaic.json")


headers = {OptionalHeader.server_timing, OptionalHeader.x_assets}


app = FastAPI(title="Mars tile server")


def elevation_mosaic_paths(x: int, y: int, z: int):
    # tile = Tile(x, y, z)
    return None


def HiRISEParams(
    image_id: str = Query(..., description="HiRISE image ID"), image_type: str = "RED"
) -> str:
    """Create dataset path from args"""
    return dataset_path(f"/hirise-images/{image_id}_{image_type}.tif")


@dataclass
class ImageryDatasetParams(DatasetParams):
    resampling_method: ResamplingName = Query(
        ResamplingName.bilinear,  # type: ignore
        alias="resampling",
        description="Resampling method.",
    )


@dataclass
class MosaicRenderParams(PostProcessParams):
    ...


def SingleMosaicParams(mosaic: str = Query(..., description="Mosaic ID")) -> List[str]:
    """Mosaic ID"""
    return [mosaic]


def MultiMosaicParams(
    mosaic: str = Query(
        "", title="Mosaics", description="comma-delimited mosaics to include"
    )
) -> List[str]:
    if mosaic == "":
        return []
    return mosaic.split(",")


single_mosaic = MosaicRouteFactory(
    reader=MarsMosaicBackend,
    path_dependency=SingleMosaicParams,
    optional_headers=headers,
    dataset_dependency=ImageryDatasetParams,
    process_dependency=MosaicRenderParams,
)

multi_mosaic = MosaicRouteFactory(
    reader=MarsMosaicBackend,
    path_dependency=MultiMosaicParams,
    optional_headers=headers,
    process_dependency=ImageryDatasetParams,
)

hirise_cog = TilerFactory(
    reader=MarsCOGReader,
    path_dependency=HiRISEParams,
    dataset_dependency=ImageryDatasetParams,
    process_dependency=MosaicRenderParams,
)
app.include_router(hirise_cog.router, tags=["Single HiRISE images"], prefix="/hirise")


@dataclass
class ElevationMosaicParams(DatasetParams):
    resampling_method: ResamplingName = Query(
        ResamplingName.bilinear,  # type: ignore
        alias="resampling",
        description="Resampling method.",
    )


# This is the main dataset
elevation_mosaic = MosaicRouteFactory(
    path_dependency=lambda: ["elevation_model"],
    dataset_dependency=ElevationMosaicParams,
    reader=ElevationMosaicBackend,
    optional_headers=headers,
)
app.include_router(
    elevation_mosaic.router, tags=["Elevation Mosaic"], prefix="/elevation-mosaic"
)

app.include_router(multi_mosaic.router, tags=["Multi-Mosaic"], prefix="/mosaic")

app.include_router(
    single_mosaic.router, tags=["Imagery Mosaic"], prefix="/mosaic/{mosaic}"
)


@app.get("/datasets/{mosaic}")
def dataset(mosaic: str, lon: float = None, lat: float = None, zoom: int = 4):
    tile = mercator_tms.tile(lon, lat, zoom)
    xy_bounds = mercator_tms.xy_bounds(tile)
    bounds = mercator_tms.bounds(tile)

    datasets = get_datasets(tile, [mosaic])

    return {
        "mercator_bounds": xy_bounds,
        "latlng_bounds": bounds,
        "tile": tile,
        "datasets": [d for d in datasets],
    }


@app.get("/mosaic")
def mosaics():
    db = get_sync_database()
    res = db.session.query(db.model.imagery_mosaic).all()
    return list(res)


add_exception_handlers(app, DEFAULT_STATUS_CODES)
add_exception_handlers(app, MOSAIC_STATUS_CODES)


@app.get("/healthcheck")
def healthcheck():
    return {"status": "ok"}


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
