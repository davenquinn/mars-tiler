"""TiTiler.mosaic Router factories."""

import os
from dataclasses import dataclass
from typing import Dict, Type

import rasterio
from rio_tiler.constants import MAX_THREADS
from titiler.mosaic.factory import MosaicTilerFactory
from titiler.core.factory import img_endpoint_params
from titiler.core.resources.enums import ImageType, OptionalHeader
from titiler.mosaic.resources.enums import PixelSelectionMethod
from fastapi import Depends, Path, Query
from starlette.responses import Response, JSONResponse
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
from .database import get_database

log = get_logger(__name__)

stmt = open(relative_path(__file__, "get-paths.sql"), "r").read()


async def get_datasets(tile, mosaic):
    if tile.z <= 8 and mosaic == "elevation_model":
        return [
            "/mars-data/global-dems/Mars_HRSC_MOLA_BlendDEM_Global_200mp_v2.cog.tif"
        ]

    bbox = bounds(tile.x, tile.y, tile.z)

    # Morecantile is really slow!
    # (x1, y1, x2, y2) = mars_tms.bounds(tile)
    Timer.add_step("tilebounds")
    db = await get_database()
    Timer.add_step("dbconnect")
    res = await db.fetch_all(
        query=stmt,
        values=dict(
            mosaic=mosaic,
            x1=bbox.west,
            y1=bbox.south,
            x2=bbox.east,
            y2=bbox.north,
            minzoom=tile.z + 2,
        ),
    )
    Timer.add_step("findassets")
    return [str(d._mapping["path"]) for d in res]


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
            headers: Dict[str, str] = {}

            tilesize = scale * 256

            threads = int(os.getenv("MOSAIC_CONCURRENCY", MAX_THREADS))
            timer = Timer()
            with timer.context() as t:
                # with rasterio.Env(**self.gdal_config):
                async with self.reader(
                    src_path,
                    reader=self.dataset_reader,
                    reader_options=self.reader_options,
                    **self.backend_options,
                ) as src_dst:
                    t.add_step("mosaicread")

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
                # timings.append(("dataread", round((t.elapsed - mosaic_read) * 1000, 2)))

                if not format:
                    format = ImageType.jpeg if data.mask.all() else ImageType.png

                image = data.post_process(
                    in_range=render_params.rescale_range,
                    color_formula=render_params.color_formula,
                )
                t.add_step("postprocess")

                content = image.render(
                    add_mask=render_params.return_mask,
                    img_format=format.driver,
                    colormap=colormap,
                    **format.profile,
                    **render_params.kwargs,
                )
                t.add_step("format")

            if OptionalHeader.server_timing in self.optional_headers:
                headers["Server-Timing"] = timer.server_timings()

            if OptionalHeader.x_assets in self.optional_headers:
                headers["X-Assets"] = ",".join(data.assets)

            return Response(content, media_type=format.mediatype, headers=headers)

    def assets(self):
        """Register /assets endpoint."""

        @self.router.get(
            r"/tiles/{z}/{x}/{y}/info",
            responses={200: {"description": "Return list of COGs"}},
        )
        async def assets_for_tile(
            z: int = Path(..., ge=0, le=30, description="Mercator tiles's zoom level"),
            x: int = Path(..., description="Mercator tiles's column"),
            y: int = Path(..., description="Mercator tiles's row"),
            src_path=Depends(self.path_dependency),
        ):
            """Return a list of assets which overlap a given tile"""
            timer = Timer()
            with timer.context() as t:
                bbox = mars_tms.bounds(Tile(x, y, z))
                t.add_step("tilebbox")
                async with self.reader(src_path, **self.backend_options) as mosaic:
                    t.add_step("setupreader")
                    assets = await mosaic.assets_for_tile(x, y, z)
                    t.add_step("findassets")
                coords = ", ".join([f"{pos:.5f}" for pos in bbox])
                env = f"ST_MakeEnvelope({coords})"

            headers = {}
            headers["Server-Timing"] = timer.server_timings()
            return JSONResponse(
                {"assets": assets, "xy_bounds": bbox, "envelope": env}, headers=headers
            )
