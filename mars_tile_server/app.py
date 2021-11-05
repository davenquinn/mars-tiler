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
from .util import ElevationReader, FakeEarthCOGReader
from .database import db
from morecantile import tms, Tile


def build_path():
    return "/mars-data/hirise-images/hirise-red.mosaic.json"


headers = {OptionalHeader.server_timing, OptionalHeader.x_assets}


def MarsMosaicBackend(*args, **kwargs):
    kwargs["reader"] = FakeEarthCOGReader
    return MosaicBackend(*args, **kwargs)


mosaic = MosaicTilerFactory(
    reader=MarsMosaicBackend, path_dependency=build_path, optional_headers=headers
)

app = FastAPI(title="Mars tile server")


def elevation_path():
    return "/mars-data/global-dems/Mars_HRSC_MOLA_BlendDEM_Global_200mp_v2.cog.tif"


cog = TilerFactory(
    path_dependency=elevation_path, reader=FakeEarthCOGReader, optional_headers=headers
)
cog_elevation = TilerFactory(
    path_dependency=elevation_path, reader=ElevationReader, optional_headers=headers
)


app.include_router(mosaic.router, tags=["HiRISE Mosaic"], prefix="/hirise-mosaic")
app.include_router(cog.router, tags=["Global DEM"], prefix="/global-dem")
app.include_router(
    cog_elevation.router, tags=["Global RGB DEM"], prefix="/global-dem-rgb"
)


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
    reader=FakeEarthCOGReader,
    path_dependency=HiRISEParams,
    dataset_dependency=HiRISEImageParams,
    render_dependency=HiRISERenderParams,
)
app.include_router(hirise_cog.router, tags=["HiRISE images"], prefix="/hirise")

mercator = tms.get("WebMercatorQuad")


@app.get("/datasets/{mosaic}")
async def read_item(mosaic: str, lon: float = None, lat: float = None, zoom: int = 5):
    tile = tms._tile(lon, lat, 4)
    bounds = tms.xy_bounds(tile)
    return bounds


add_exception_handlers(app, DEFAULT_STATUS_CODES)
add_exception_handlers(app, MOSAIC_STATUS_CODES)


@app.on_event("startup")
async def startup_event():
    logger = logging.getLogger("mars_tile_server")
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)
