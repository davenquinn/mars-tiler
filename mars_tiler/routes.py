"""Mosaic definitions (a close approximation of Cogeo-Mosaic BaseBackend)"""

from http.client import NotConnected
import os
from dataclasses import dataclass
from typing import Dict, Type, List, Optional
from json import loads
from rio_tiler.constants import MAX_THREADS
from titiler.mosaic.factory import MosaicTilerFactory
from titiler.core.factory import img_endpoint_params
from titiler.core.resources.enums import ImageType, OptionalHeader
from titiler.mosaic.resources.enums import PixelSelectionMethod
from fastapi import Depends, Path, Query
from starlette.responses import Response, JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi import BackgroundTasks
from cogeo_mosaic.errors import NoAssetFoundError

from morecantile import Tile
from sparrow.utils import get_logger

from .timer import Timer
from .defs import mars_tms
from .database import get_sync_database, prepared_statement, get_database
from .mosaic.base import PGMosaicBackend, MosaicAsset, create_asset


log = get_logger(__name__)


@dataclass
class MosaicRouteFactory(MosaicTilerFactory):
    reader: Type[PGMosaicBackend] = PGMosaicBackend

    def register_routes(self):
        self.root()
        self.tile()
        self.assets()

    def root(self):
        @self.router.get("/")
        def root(mosaic=Depends(self.path_dependency)):
            return {"mosaic": mosaic}

    def get_cached_tile(self, mosaics, x, y, z):
        db = get_sync_database()
        tile_info = db.session.execute(
            "SELECT (imagery.get_tile_info(:x, :y, :z, :mosaics)).*",
            dict(x=x, y=y, z=z, mosaics=mosaics),
        ).first()
        return tile_info

    def set_cached_tile(self, mosaics, x, y, z, tile):
        db = get_sync_database()
        db.session.execute(
            prepared_statement("set-cached-tile"),
            dict(
                x=x,
                y=y,
                z=z,
                tile=tile,
                layers=mosaics,
            ),
        )

    def tile(self):  # noqa: C901
        """Register /tiles endpoints."""

        @self.router.get(r"/tiles/{z}/{x}/{y}", **img_endpoint_params)
        @self.router.get(r"/tiles/{z}/{x}/{y}.{format}", **img_endpoint_params)
        @self.router.get(r"/tiles/{z}/{x}/{y}@{scale}x", **img_endpoint_params)
        @self.router.get(r"/tiles/{z}/{x}/{y}@{scale}x.{format}", **img_endpoint_params)
        def tile(
            background_tasks: BackgroundTasks,
            z: int = Path(..., ge=0, le=30, description="Mercator tiles's zoom level"),
            x: int = Path(..., description="Mercator tiles's column"),
            y: int = Path(..., description="Mercator tiles's row"),
            scale: int = Query(
                1, gt=0, lt=4, description="Tile size scale. 1=256x256, 2=512x512..."
            ),
            format: ImageType = Query(
                None, description="Output image type. Default is auto."
            ),
            use_cache: bool = Query(
                True, description="Allow the tile cache to be accessed."
            ),
            src_path=Depends(self.path_dependency),
            layer_params=Depends(self.layer_dependency),
            dataset_params=Depends(self.dataset_dependency),
            pixel_selection: PixelSelectionMethod = Query(
                PixelSelectionMethod.first, description="Pixel selection method."
            ),
            postprocess_params=Depends(self.process_dependency),
            colormap=Depends(self.colormap_dependency),
            render_params=Depends(self.render_dependency),
        ):
            """Create map tile from a COG."""

            tilesize = scale * 256

            tile_assets: Optional[List[MosaicAsset]] = None

            should_cache_tile = use_cache
            if len(src_path) > 1:
                # We don't support caching multiple mosaics yet
                use_cache = False

            threads = int(os.getenv("MOSAIC_CONCURRENCY", MAX_THREADS))
            timer = Timer()
            with timer.context() as t:
                # with rasterio.Env(**self.gdal_config):
                if use_cache:
                    should_cache_tile = True
                    tile_info = self.get_cached_tile(src_path, x, y, z)
                    t.add_step("check_cache")
                    tile_assets = [create_asset(d) for d in tile_info.datasets]
                    if tile_info.cached_tile is not None:
                        headers = self._tile_headers(timer, tile_assets)
                        headers["X-Tile-Cache"] = "hit"
                        return Response(
                            content=bytes(tile_info.cached_tile),
                            media_type=tile_info.content_type,
                            headers=headers,
                        )
                    if not tile_info.should_generate:
                        raise NoAssetFoundError()

                with self.reader(
                    src_path,
                    reader=self.dataset_reader,
                    **self.backend_options,
                ) as src_dst:
                    t.add_step("mosaicread")
                    data, _ = src_dst.tile(
                        x,
                        y,
                        z,
                        assets=tile_assets,
                        pixel_selection=pixel_selection.method(),
                        tilesize=tilesize,
                        threads=threads,
                        **layer_params,
                        **dataset_params,
                    )
                # timings.append(("dataread", round((t.elapsed - mosaic_read) * 1000, 2)))

                if not format:
                    format = ImageType.jpeg if data.mask.all() else ImageType.png

                image = data.post_process(**postprocess_params)
                t.add_step("postprocess")

                content = image.render(
                    img_format=format.driver,
                    colormap=colormap,
                    **format.profile,
                    **render_params,
                )
                t.add_step("format")

            # Add the tile to the cache after returning it to the user.
            if should_cache_tile:
                background_tasks.add_task(
                    self.set_cached_tile, src_path, x, y, z, content
                )

            headers = self._tile_headers(timer, data.assets)
            headers["X-Tile-Cache"] = "miss" if use_cache else "bypass"

            return Response(content, media_type=format.mediatype, headers=headers)

    def _tile_headers(self, timer, sources: List[MosaicAsset]):
        headers: Dict[str, str] = {}
        if OptionalHeader.server_timing in self.optional_headers:
            headers["Server-Timing"] = timer.server_timings()
        if OptionalHeader.x_assets in self.optional_headers:
            headers["X-Assets"] = ",".join([sources.path for sources in sources])
        return headers

    def assets(self):
        """Register /assets endpoint."""

        @self.router.get(
            r"/tiles/{z}/{x}/{y}/info",
            responses={200: {"description": "Return list of COGs"}},
        )
        def assets_for_tile(
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
                with self.reader(src_path, **self.backend_options) as mosaic:
                    t.add_step("setupreader")
                    assets = mosaic.assets_for_tile(x, y, z)
                    t.add_step("findassets")
                coords = ", ".join([f"{pos:.5f}" for pos in bbox])
                env = f"ST_MakeEnvelope({coords})"

            headers = {}
            headers["Server-Timing"] = timer.server_timings()
            return JSONResponse(
                {
                    "assets": [jsonable_encoder(a) for a in assets],
                    "xy_bounds": bbox,
                    "envelope": env,
                    "mosaics": src_path,
                },
                headers=headers,
            )

        @self.router.get(
            "/assets", responses={200: {"description": "Return all footprints."}}
        )
        def assets(mosaic=Depends(self.path_dependency)):
            db = get_sync_database()
            data = db.session.execute(
                prepared_statement("get-datasets"),
                dict(
                    mosaic=mosaic,
                ),
            )
            return {
                "type": "FeatureCollection",
                "features": list(data),
            }
