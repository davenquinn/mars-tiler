async def get_all_datasets(tile, mosaic):
    bbox = bounds(tile.x, tile.y, tile.z)

    # Morecantile is really slow!
    # (x1, y1, x2, y2) = mars_tms.bounds(tile)
    Timer.add_step("tilebounds")
    db = await get_database()
    Timer.add_step("dbconnect")
    res = await db.fetch_all(
        query=prepared_statement("get-paths"),
        values=dict(
            mosaic=mosaic,
            x1=bbox.west,
            y1=bbox.south,
            x2=bbox.east,
            y2=bbox.north,
        ),
    )
    Timer.add_step("findassets")
    return [
        str(d._mapping["path"]) for d in res if int(d._mapping["minzoom"]) - 4 < tile.z
    ]


"""TiTiler.mosaic Router factories."""

import os
from dataclasses import dataclass
from typing import Dict, Type
from json import loads

from typing import Any, Dict, List, Tuple, Type

import attr
from morecantile import TileMatrixSet, Tile
from rasterio.crs import CRS
from rio_tiler.constants import WEB_MERCATOR_TMS
from rio_tiler.errors import PointOutsideBounds
from rio_tiler.io import BaseReader, AsyncBaseReader, COGReader
from rio_tiler.models import ImageData
from rio_tiler.mosaic import mosaic_reader
from rio_tiler.tasks import multi_values
from cogeo_mosaic.errors import NoAssetFoundError
from sparrow.utils import relative_path, get_logger
from mercantile import bounds

from .timer import Timer
from .defs import mars_tms
from .database import get_database, prepared_statement
from .base import AsyncBaseBackend, get_datasets

log = get_logger(__name__)


async def get_datasets_multi(tile, mosaics=[]):
    if len(mosaics) == 0:
        return []
    if len(mosaics) == 1:
        return get_datasets(tile, mosaics[0])

    bbox = bounds(tile.x, tile.y, tile.z)
    # Morecantile is really slow!
    # (x1, y1, x2, y2) = mars_tms.bounds(tile)
    Timer.add_step("tilebounds")
    db = await get_database()
    Timer.add_step("dbconnect")
    res = await db.fetch_all(
        query=prepared_statement("get-all-paths"),
        values=dict(
            x1=bbox.west,
            y1=bbox.south,
            x2=bbox.east,
            y2=bbox.north,
        ),
    )
    Timer.add_step("findassets")
    return [
        str(d._mapping["path"])
        for d in res
        if int(d._mapping["minzoom"]) - 4 < tile.z and d._mapping["mosaic"] in mosaics
    ]


class MultiMosaicBackend(AsyncBaseBackend):
    mosaics: str = attr.ib()

    async def get_assets(self, x: int, y: int, z: int) -> List[str]:
        return await get_all_datasets(Tile(x, y, z), self.mosaics)
