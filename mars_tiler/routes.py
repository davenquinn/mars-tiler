"""Mosaic definitions (a close approximation of Cogeo-Mosaic BaseBackend)"""

import os
from dataclasses import dataclass
from typing import Dict, Type
from json import loads
from rio_tiler.constants import MAX_THREADS
from titiler.mosaic.factory import MosaicTilerFactory
from titiler.core.factory import img_endpoint_params
from titiler.core.resources.enums import ImageType, OptionalHeader
from titiler.mosaic.resources.enums import PixelSelectionMethod
from fastapi import Depends, Path, Query
from starlette.responses import Response, JSONResponse
from fastapi.encoders import jsonable_encoder

from morecantile import Tile
from sparrow.utils import get_logger

from .timer import Timer
from .defs import mars_tms
from .database import get_sync_database, prepared_statement
from .mosaic.base import PGMosaicBackend, get_datasets


log = get_logger(__name__)

stmt_cache = {}


def prepare_record(d):
    data = dict(**d)
    data["geometry"] = loads(d["geometry"])
    return data


@dataclass
class MosaicRouteFactory(MosaicTilerFactory):
    reader: Type[PGMosaicBackend] = PGMosaicBackend

    def register_routes(self):
        self.tile()
        self.assets()

    def tile(self):  # noqa: C901
        """Register /tiles endpoints."""

        @self.router.get(r"/tiles/{z}/{x}/{y}", **img_endpoint_params)
        @self.router.get(r"/tiles/{z}/{x}/{y}.{format}", **img_endpoint_params)
        @self.router.get(r"/tiles/{z}/{x}/{y}@{scale}x", **img_endpoint_params)
        @self.router.get(r"/tiles/{z}/{x}/{y}@{scale}x.{format}", **img_endpoint_params)
        def tile(
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
            pixel_selection: PixelSelectionMethod = Query(
                PixelSelectionMethod.first, description="Pixel selection method."
            ),
            postprocess_params=Depends(self.process_dependency),
            colormap=Depends(self.colormap_dependency),
            render_params=Depends(self.render_dependency),
        ):
            """Create map tile from a COG."""
            headers: Dict[str, str] = {}

            tilesize = scale * 256

            threads = int(os.getenv("MOSAIC_CONCURRENCY", MAX_THREADS))
            timer = Timer()
            with timer.context() as t:
                # with rasterio.Env(**self.gdal_config):
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

            if OptionalHeader.server_timing in self.optional_headers:
                headers["Server-Timing"] = timer.server_timings()

            if OptionalHeader.x_assets in self.optional_headers:
                headers["X-Assets"] = ",".join([d.path for d in data.assets])

            maxzoom = max([d.maxzoom for d in data.assets])
            headers["X-Max-Zoom"] = str(maxzoom)

            return Response(content, media_type=format.mediatype, headers=headers)

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
                "features": [prepare_record(d) for d in data],
            }
