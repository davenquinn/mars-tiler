from morecantile import tms
from sparrow.utils import get_logger
from titiler.core.utils import Timer

import attr
from .async_mosaic import AsyncMosaicBackend
from .util import MarsCOGReader, HiRISEReader, data_to_rgb
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
