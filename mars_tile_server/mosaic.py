from cachetools import TTLCache, cached
from cachetools.keys import hashkey
from typing import List
from cogeo_mosaic.mosaic import MosaicJSON
from cogeo_mosaic.backends.utils import find_quadkeys
from cogeo_mosaic.cache import cache_config
from cogeo_mosaic.backends import BaseBackend
from morecantile import tms, Tile
from .util import FakeEarthCOGReader, ElevationReader, MarsCOGReader
import attr

from typing import List

from .database import get_database
from geoalchemy2.functions import ST_MakeEnvelope, ST_SetSRID
from sqlalchemy import and_, desc
from sparrow.utils import get_logger

mercator_tms = tms.get("WebMercatorQuad")

log = get_logger(__name__)


def get_datasets(tile: Tile, mosaic: str):
    bounds = mercator_tms.bounds(tile)

    db = get_database()

    Dataset = db.model.imagery_dataset

    datasets = (
        db.session.query(Dataset)
        .filter(Dataset.mosaic == mosaic)
        .filter(
            Dataset.footprint.ST_Intersects(
                ST_SetSRID(ST_MakeEnvelope(*bounds), 949900)
            )
        )
        .filter(Dataset.minzoom <= tile.z)
        .order_by(desc(Dataset.maxzoom))
    )
    _datasets = datasets.all()
    log.info(bounds)
    log.info([d.path for d in _datasets])

    return _datasets


@attr.s
class MarsMosaicBackend(BaseBackend):
    mosaicid: str = "hirise_red"

    def __attrs_post_init__(self):
        self.reader = MarsCOGReader

    @cached(
        TTLCache(maxsize=cache_config.maxsize, ttl=cache_config.ttl),
        key=lambda self, x, y, z: hashkey(self.mosaicid, x, y, z),
    )
    def get_assets(self, x: int, y: int, z: int) -> List[str]:
        tile = Tile(x, y, z)
        return [d.path for d in get_datasets(tile, self.mosaicid)]

    def _read(self):
        return MosaicJSON(
            mosaicjson="", minzoom=0, maxzoom=18, tiles=[], quadkey_zoom=10
        )

    def write(self, overwrite=False):
        pass

    def tile(self, *args, **kwargs):
        return super().tile(*args, **kwargs)


@attr.s
class ElevationMosaicBackend(MarsMosaicBackend):
    mosaicid: str = "elevation_model"

    def __attrs_post_init__(self):
        self.reader = ElevationReader
