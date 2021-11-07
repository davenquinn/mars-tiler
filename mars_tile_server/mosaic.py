from cachetools import TTLCache, cached
from cachetools.keys import hashkey
from typing import List
from cogeo_mosaic.mosaic import MosaicJSON
from cogeo_mosaic.backends.utils import find_quadkeys
from cogeo_mosaic.cache import cache_config
from cogeo_mosaic.backends import BaseBackend
from morecantile import tms, Tile
from .util import FakeEarthCOGReader, ElevationReader
import attr

from typing import List

from .database import get_database
from geoalchemy2.functions import ST_MakeEnvelope, ST_SetSRID
from sqlalchemy import and_

mercator = tms.get("WebMercatorQuad")


def get_datasets(lon: int, lat: int, zoom: int, mosaic: str):
    tile = Tile(lon, lat, zoom)
    bounds = mercator.bounds(tile)

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
        .filter(and_(Dataset.minzoom <= zoom, zoom <= Dataset.maxzoom))
    )

    return datasets.all()


@attr.s
class CustomMosaicBackend(BaseBackend):
    mosaicid: str = "elevation_model"

    def __attrs_post_init__(self):
        self.reader = ElevationReader

    @cached(
        TTLCache(maxsize=cache_config.maxsize, ttl=cache_config.ttl),
        key=lambda self, x, y, z: hashkey(self.mosaicid, x, y, z),
    )
    def get_assets(self, x: int, y: int, z: int) -> List[str]:
        return [d.path for d in get_datasets(x, y, z, self.mosaicid)]

    def _read(self):
        return MosaicJSON(mosaicjson="", minzoom=0, maxzoom=18, tiles=[])

    def write(self, overwrite=False):
        pass
