from typing import List
from cachetools import TTLCache, cached
from cachetools.keys import hashkey
from cogeo_mosaic.mosaic import MosaicJSON
from cogeo_mosaic.cache import cache_config
from cogeo_mosaic.backends import BaseBackend
from morecantile import tms, Tile
from geoalchemy2.functions import ST_MakeEnvelope, ST_SetSRID
from sqlalchemy import and_, desc
from sparrow.utils import get_logger, relative_path
from titiler.core.utils import Timer
from sqlalchemy import text
from asyncio import run, get_event_loop, create_task
from concurrent.futures import ThreadPoolExecutor
import os

import attr
from .async_mosaic import AsyncMosaicBackend
from .defs import mars_tms
from .util import MarsCOGReader, HiRISEReader, data_to_rgb
from .database import get_database
from .timer import Timer

mercator_tms = tms.get("WebMercatorQuad")

log = get_logger(__name__)


def elevation_path():
    return "/mars-data/global-dems/Mars_HRSC_MOLA_BlendDEM_Global_200mp_v2.cog.tif"


@attr.s
class MarsMosaicBackend(AsyncMosaicBackend):
    def __attrs_post_init__(self):
        self.reader = MarsCOGReader


@attr.s
class ElevationMosaicBackend(MarsMosaicBackend):
    async def tile(self, *args, **kwargs):
        im, assets = await super().tile(*args, **kwargs)
        im.data = data_to_rgb(im.data[0], -10000, 0.1)
        Timer.add_step("rgbencode")
        return (im, assets)


@attr.s
class HiRISEMosaicBackend(MarsMosaicBackend):
    def __attrs_post_init__(self):
        self.reader = HiRISEReader
