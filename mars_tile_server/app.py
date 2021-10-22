from fastapi import FastAPI
from cogeo_mosaic.backends import MosaicBackend
from titiler.mosaic.factory import MosaicTilerFactory
from titiler.mosaic.errors import MOSAIC_STATUS_CODES
from titiler.core.factory import TilerFactory
from titiler.core.errors import DEFAULT_STATUS_CODES, add_exception_handlers
from .util import FakeEarthCOGReader


def build_path():
    return "/mars-data/hirise-images/hirise-red.mosaic.json"


mosaic = MosaicTilerFactory(reader=MosaicBackend, path_dependency=build_path)

app = FastAPI(title="Mars tile server")


def elevation_path():
    return "/mars-data/global-dems/Mars_HRSC_MOLA_BlendDEM_Global_200mp_v2.cog.tif"


cog = TilerFactory(path_dependency=elevation_path, reader=FakeEarthCOGReader)

app.include_router(mosaic.router, tags=["HiRISE"], prefix="/hirise")
app.include_router(cog.router, tags=["Global DEM"], prefix="/global-dem")
add_exception_handlers(app, DEFAULT_STATUS_CODES)
add_exception_handlers(app, MOSAIC_STATUS_CODES)
