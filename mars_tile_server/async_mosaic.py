"""TiTiler.mosaic Router factories."""

import os
from dataclasses import dataclass
from typing import Dict, Type

import rasterio
from rio_tiler.constants import MAX_THREADS
from titiler.core.utils import Timer
from titiler.mosaic.factory import MosaicTilerFactory
from titiler.core.factory import img_endpoint_params
from titiler.core.resources.enums import ImageType, OptionalHeader
from titiler.mosaic.resources.enums import PixelSelectionMethod
from fastapi import Depends, Path, Query
from starlette.responses import Response


import itertools
from typing import Any, Dict, List, Optional, Tuple, Type

import attr
import mercantile
from cachetools import TTLCache, cached
from cachetools.keys import hashkey
from morecantile import TileMatrixSet
from rasterio.crs import CRS
from rio_tiler.constants import WEB_MERCATOR_TMS
from rio_tiler.errors import PointOutsideBounds
from rio_tiler.io import BaseReader, AsyncBaseReader, COGReader
from rio_tiler.models import ImageData
from rio_tiler.mosaic import mosaic_reader
from rio_tiler.tasks import multi_values

from cogeo_mosaic.backends.utils import find_quadkeys
from cogeo_mosaic.cache import cache_config
from cogeo_mosaic.errors import NoAssetFoundError
from cogeo_mosaic.mosaic import MosaicJSON
from morecantile import Tile

from sparrow.utils import relative_path, get_logger

from .defs import mars_tms
from sqlalchemy import text
from .database import get_database

log = get_logger(__name__)

stmt = text(open(relative_path(__file__, "get-paths.sql"), "r").read())


def get_datasets(tile, mosaic):
    (x1, y1, x2, y2) = mars_tms.bounds(tile)
    conn = get_database()
    res = conn.execute(stmt, mosaic=mosaic, x1=x1, y1=y1, x2=x2, y2=y2, minzoom=tile.z)
    return [d.path for d in res]


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

    def assets_for_tile(self, x: int, y: int, z: int) -> List[str]:
        """Retrieve assets for tile."""
        return self.get_assets(x, y, z)

    def assets_for_point(self, lng: float, lat: float) -> List[str]:
        """Retrieve assets for point."""
        tile = mercantile.tile(lng, lat, self.quadkey_zoom)
        return self.get_assets(tile.x, tile.y, tile.z)

    def assets_for_bbox(
        self, xmin: float, ymin: float, xmax: float, ymax: float
    ) -> List[str]:
        """Retrieve assets for bbox."""
        tl_tile = mercantile.tile(xmin, ymax, self.quadkey_zoom)
        br_tile = mercantile.tile(xmax, ymin, self.quadkey_zoom)

        tiles = [
            (x, y, self.quadkey_zoom)
            for x in range(tl_tile.x, br_tile.x + 1)
            for y in range(tl_tile.y, br_tile.y + 1)
        ]

        return list(
            dict.fromkeys(
                itertools.chain.from_iterable([self.assets_for_tile(*t) for t in tiles])
            )
        )

    def _get_assets(self, tile: Tile) -> List[str]:
        return get_datasets(tile, self.mosaicid)

    def get_assets(self, x: int, y: int, z: int) -> List[str]:
        with Timer() as t:
            assets = self._get_assets(Tile(x, y, z))
        log.info(f"Got assets for tile {z}/{x}/{y}: took {t.elapsed:.2f}s")
        return assets

    async def tile(  # type: ignore
        self,
        x: int,
        y: int,
        z: int,
        reverse: bool = False,
        **kwargs: Any,
    ) -> Tuple[ImageData, List[str]]:
        """Get Tile from multiple observation."""
        mosaic_assets = self.assets_for_tile(x, y, z)
        if not mosaic_assets:
            raise NoAssetFoundError(f"No assets found for tile {z}-{x}-{y}")

        if reverse:
            mosaic_assets = list(reversed(mosaic_assets))

        def _reader(asset: str, x: int, y: int, z: int, **kwargs: Any) -> ImageData:
            with self.reader(asset, **self.reader_options) as src_dst:
                return src_dst.tile(x, y, z, **kwargs)

        return mosaic_reader(mosaic_assets, _reader, x, y, z, **kwargs)

    async def point(
        self,
        lon: float,
        lat: float,
        reverse: bool = False,
        **kwargs: Any,
    ) -> List:
        """Get Point value from multiple observation."""
        mosaic_assets = self.assets_for_point(lon, lat)
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


class AsyncMosaicBackend(AsyncBaseBackend):
    ...


@dataclass
class AsyncMosaicFactory(MosaicTilerFactory):
    reader: Type[AsyncMosaicBackend] = AsyncMosaicBackend

    def register_routes(self):
        self.tile()
        self.assets()

    def tile(self):  # noqa: C901
        """Register /tiles endpoints."""

        @self.router.get(r"/tiles/{z}/{x}/{y}", **img_endpoint_params)
        @self.router.get(r"/tiles/{z}/{x}/{y}.{format}", **img_endpoint_params)
        @self.router.get(r"/tiles/{z}/{x}/{y}@{scale}x", **img_endpoint_params)
        @self.router.get(r"/tiles/{z}/{x}/{y}@{scale}x.{format}", **img_endpoint_params)
        async def tile(
            z: int = Path(..., ge=0, le=30, description="Mercator tiles's zoom level"),
            x: int = Path(..., description="Mercator tiles's column"),
            y: int = Path(..., description="Mercator tiles's row"),
            scale: int = Query(
                1, gt=0, lt=4, description="Tile size scale. 1=256x256, 2=512x512..."
            ),
            format: ImageType = Query(
                None, description="Output image type. Default is auto."
            ),
            src_path=Depends(self.path_dependency),
            layer_params=Depends(self.layer_dependency),
            dataset_params=Depends(self.dataset_dependency),
            render_params=Depends(self.render_dependency),
            colormap=Depends(self.colormap_dependency),
            pixel_selection: PixelSelectionMethod = Query(
                PixelSelectionMethod.first, description="Pixel selection method."
            ),
            kwargs: Dict = Depends(self.additional_dependency),
        ):
            """Create map tile from a COG."""
            timings = []
            headers: Dict[str, str] = {}

            tilesize = scale * 256

            threads = int(os.getenv("MOSAIC_CONCURRENCY", MAX_THREADS))
            with Timer() as t:
                with rasterio.Env(**self.gdal_config):
                    async with self.reader(
                        src_path,
                        reader=self.dataset_reader,
                        reader_options=self.reader_options,
                        **self.backend_options,
                    ) as src_dst:
                        mosaic_read = t.from_start
                        timings.append(("mosaicread", round(mosaic_read * 1000, 2)))

                        data, _ = await src_dst.tile(
                            x,
                            y,
                            z,
                            pixel_selection=pixel_selection.method(),
                            tilesize=tilesize,
                            threads=threads,
                            **layer_params.kwargs,
                            **dataset_params.kwargs,
                            **kwargs,
                        )
            timings.append(("dataread", round((t.elapsed - mosaic_read) * 1000, 2)))

            if not format:
                format = ImageType.jpeg if data.mask.all() else ImageType.png

            with Timer() as t:
                image = data.post_process(
                    in_range=render_params.rescale_range,
                    color_formula=render_params.color_formula,
                )
            timings.append(("postprocess", round(t.elapsed * 1000, 2)))

            with Timer() as t:
                content = image.render(
                    add_mask=render_params.return_mask,
                    img_format=format.driver,
                    colormap=colormap,
                    **format.profile,
                    **render_params.kwargs,
                )
            timings.append(("format", round(t.elapsed * 1000, 2)))

            if OptionalHeader.server_timing in self.optional_headers:
                headers["Server-Timing"] = ", ".join(
                    [f"{name};dur={time}" for (name, time) in timings]
                )

            if OptionalHeader.x_assets in self.optional_headers:
                headers["X-Assets"] = ",".join(data.assets)

            return Response(content, media_type=format.mediatype, headers=headers)
