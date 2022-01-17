import attr
from morecantile import tms
from sparrow.utils import get_logger
from titiler.core.utils import Timer

from ..defs import mars_tms, MARS_MERCATOR, MARS2000_SPHERE
from ..util import MarsCOGReader, HiRISEReader, data_to_rgb
from ..timer import Timer
from .base import PGMosaicBackend

mercator_tms = tms.get("WebMercatorQuad")

log = get_logger(__name__)


@attr.s
class MarsMosaicBackend(PGMosaicBackend):
    def __attrs_post_init__(self):
        self.geographic_crs = MARS2000_SPHERE
        self.crs = MARS_MERCATOR
        self.tms = mars_tms
        self.reader = MarsCOGReader


@attr.s
class ElevationMosaicBackend(MarsMosaicBackend):
    def tile(self, *args, **kwargs):
        im, assets = super().tile(*args, **kwargs)
        im.data = data_to_rgb(im.data[0], -10000, 0.1)
        Timer.add_step("rgbencode")
        return (im, assets)


@attr.s
class HiRISEMosaicBackend(MarsMosaicBackend):
    def __attrs_post_init__(self):
        self.reader = HiRISEReader
