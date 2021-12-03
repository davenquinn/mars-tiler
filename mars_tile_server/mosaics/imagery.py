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


@attr.s
class AsyncBaseBackend(AsyncBaseReader):
    """Base Class for cogeo-mosaic backend storage, modified for async use
    Original file is `cogeo_mosaic.backends.base`

    Attributes:
        input (str): mosaic path.
        reader (rio_tiler.io.BaseReader): Dataset reader. Defaults to `rio_tiler.io.COGReader`.
        reader_options (dict): Options to forward to the reader config.
        tms (morecantile.TileMatrixSet, optional): TileMatrixSet grid definition. **READ ONLY attribute**. Defaults to `WebMercatorQuad`.
        bbox (tuple): mosaic bounds (left, bottom, right, top). **READ ONLY attribute**. Defaults to `(-180, -90, 180, 90)`.
        minzoom (int): mosaic Min zoom level. **READ ONLY attribute**. Defaults to `0`.
        maxzoom (int): mosaic Max zoom level. **READ ONLY attribute**. Defaults to `30`

    """

    mosaicid: str = attr.ib()

    reader: Type[BaseReader] = attr.ib(default=COGReader)
    reader_options: Dict = attr.ib(factory=dict)
    quadkey_zoom: int = attr.ib(default=10)

    # TMS is outside the init because mosaicJSON and cogeo-mosaic only
    # works with WebMercator (mercantile) for now.
    tms: TileMatrixSet = attr.ib(init=False, default=WEB_MERCATOR_TMS)
    minzoom: int = attr.ib(init=False)
    maxzoom: int = attr.ib(init=False)

    # default values for bounds
    bounds: Tuple[float, float, float, float] = attr.ib(
        init=False, default=(-180, -90, 180, 90)
    )
    crs: CRS = attr.ib(init=False, default=CRS.from_epsg(4326))

    async def assets_for_tile(self, x: int, y: int, z: int) -> List[str]:
        """Retrieve assets for tile."""
        return await self.get_assets(x, y, z)

    async def assets_for_point(self, lng: float, lat: float) -> List[str]:
        """Retrieve assets for point."""
        tile = self.tms.tile(lng, lat, self.quadkey_zoom)
        return await self.get_assets(tile.x, tile.y, tile.z)

    async def _get_assets(self, tile: Tile) -> List[str]:
        return await get_datasets(tile, self.mosaicid)

    async def get_assets(self, x: int, y: int, z: int) -> List[str]:
        return await self._get_assets(Tile(x, y, z))

    async def tile(  # type: ignore
        self,
        x: int,
        y: int,
        z: int,
        reverse: bool = False,
        **kwargs: Any,
    ) -> Tuple[ImageData, List[str]]:
        """Get Tile from multiple observation."""
        mosaic_assets = await self.assets_for_tile(x, y, z)
        if not mosaic_assets:
            raise NoAssetFoundError(f"No assets found for tile {z}-{x}-{y}")

        if reverse:
            mosaic_assets = list(reversed(mosaic_assets))

        def _reader(asset: str, x: int, y: int, z: int, **kwargs: Any) -> ImageData:
            with self.reader(asset, **self.reader_options) as src_dst:
                return src_dst.tile(x, y, z, **kwargs)

        data = mosaic_reader(mosaic_assets, _reader, x, y, z, **kwargs)
        Timer.add_step("readdata")
        return data

    async def point(
        self,
        lon: float,
        lat: float,
        reverse: bool = False,
        **kwargs: Any,
    ) -> List:
        """Get Point value from multiple observation."""
        mosaic_assets = await self.assets_for_point(lon, lat)
        if not mosaic_assets:
            raise NoAssetFoundError(f"No assets found for point ({lon},{lat})")

        if reverse:
            mosaic_assets = list(reversed(mosaic_assets))

        def _reader(asset: str, lon: float, lat: float, **kwargs) -> Dict:
            with self.reader(asset, **self.reader_options) as src_dst:
                return src_dst.point(lon, lat, **kwargs)

        if "allowed_exceptions" not in kwargs:
            kwargs.update({"allowed_exceptions": (PointOutsideBounds,)})

        return list(multi_values(mosaic_assets, _reader, lon, lat, **kwargs).items())

    async def info(self):
        raise NotImplementedError

    async def stats(self):
        raise NotImplementedError

    async def statistics(self):
        """PlaceHolder for BaseReader.statistics."""
        raise NotImplementedError

    async def preview(self):
        """PlaceHolder for BaseReader.preview."""
        raise NotImplementedError

    async def part(self):
        """PlaceHolder for BaseReader.part."""
        raise NotImplementedError

    async def feature(self):
        """PlaceHolder for BaseReader.feature."""
        raise NotImplementedError


class MultiMosaicBackend(AsyncBaseBackend):
    async def tile(
        self,
        x: int,
        y: int,
        z: int,
        mosaics: List[str] = [],
        reverse: bool = False,
        **kwargs: Any,
    ) -> Tuple[ImageData, List[str]]:
        """Get Tile from multiple observation."""
        mosaic_assets = await self.assets_for_tile(x, y, z)
        if not mosaic_assets:
            raise NoAssetFoundError(f"No assets found for tile {z}-{x}-{y}")
        if reverse:
            mosaic_assets = list(reversed(mosaic_assets))

        def _reader(asset: str, x: int, y: int, z: int, **kwargs: Any) -> ImageData:
            with self.reader(asset, **self.reader_options) as src_dst:
                return src_dst.tile(x, y, z, **kwargs)

        data = mosaic_reader(mosaic_assets, _reader, x, y, z, **kwargs)
        Timer.add_step("readdata")
        return data
