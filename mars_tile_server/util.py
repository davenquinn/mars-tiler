from typing import Any, Dict, Optional, Sequence, Union
from rio_tiler.io import COGReader
from rio_tiler.models import ImageData
from rio_tiler.constants import WGS84_CRS, BBox
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_bounds
from rio_tiler.reader import part
from rasterio.crs import CRS
from rio_rgbify.encoders import data_to_rgb
import rasterio


EARTH_RADIUS = 6378137


def fake_earth_crs(crs: CRS) -> CRS:
    data = crs.to_dict()
    radius = data.get("R", None)
    if radius is None:
        raise AttributeError(
            "Error faking Earth CRS: Input does not have 'R' parameter..."
        )
    if radius == EARTH_RADIUS:
        return crs
    data["R"] = EARTH_RADIUS
    return CRS.from_dict(data)


class FakeEarthCOGReader(COGReader):
    """Hopefully temporary kludge to get around the Proj library's recent insistence that
    all the good web-mapping projections are for Earth only. Opens a dataset in a
    mode that substitutes a Mars-like radius for WGS84.
    """

    def __init__(self, src_path, dataset=None, *args, **kwargs):
        if src_path is not None:
            self.src_dst = rasterio.open(src_path)
        else:
            self.src_dst = dataset
        dataset = WarpedVRT(self.src_dst, src_crs=fake_earth_crs(self.src_dst.crs))
        super().__init__(None, dataset, *args, **kwargs)

    def close(self):
        self.src_dst.close()
        super().close()


class ElevationReader(FakeEarthCOGReader):
    def part(
        self,
        bbox: BBox,
        dst_crs: Optional[CRS] = None,
        bounds_crs: CRS = WGS84_CRS,
        indexes: Optional[Union[int, Sequence]] = None,
        expression: Optional[str] = None,
        max_size: Optional[int] = None,
        height: Optional[int] = None,
        width: Optional[int] = None,
        **kwargs: Any,
    ) -> ImageData:
        """Read part of a COG.
        Args:
            bbox (tuple): Output bounds (left, bottom, right, top) in target crs ("dst_crs").
            dst_crs (rasterio.crs.CRS, optional): Overwrite target coordinate reference system.
            bounds_crs (rasterio.crs.CRS, optional): Bounds Coordinate Reference System. Defaults to `epsg:4326`.
            indexes (sequence of int or int, optional): Band indexes.
            expression (str, optional): rio-tiler expression (e.g. b1/b2+b3).
            max_size (int, optional): Limit the size of the longest dimension of the dataset read, respecting bounds X/Y aspect ratio.
            height (int, optional): Output height of the array.
            width (int, optional): Output width of the array.
            kwargs (optional): Options to forward to the `rio_tiler.reader.part` function.
        Returns:
            rio_tiler.models.ImageData: ImageData instance with data, mask and input spatial info.
        """
        kwargs = {**self._kwargs, **kwargs}

        if not dst_crs:
            dst_crs = bounds_crs

        data, mask = part(
            self.dataset,
            bbox,
            max_size=max_size,
            width=width,
            height=height,
            bounds_crs=bounds_crs,
            dst_crs=dst_crs,
            indexes=indexes,
            **kwargs,
        )

        if bounds_crs and bounds_crs != dst_crs:
            bbox = transform_bounds(bounds_crs, dst_crs, *bbox, densify_pts=21)

        print(data)

        return ImageData(
            data_to_rgb(data, -10000, 0.1),
            mask,
            bounds=bbox,
            crs=dst_crs,
            assets=[self.input],
        )


def get_cog_info(src_path: str, cog: COGReader):
    bounds = cog.bounds
    return {
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [bounds[0], bounds[3]],
                    [bounds[0], bounds[1]],
                    [bounds[2], bounds[1]],
                    [bounds[2], bounds[3]],
                    [bounds[0], bounds[3]],
                ]
            ],
        },
        "properties": {
            "path": src_path,
            "bounds": cog.bounds,
            "minzoom": cog.minzoom,
            "maxzoom": cog.maxzoom,
            "datatype": cog.dataset.meta["dtype"],
        },
        "type": "Feature",
    }


def get_dataset_info(src_path: str) -> Dict:
    """Get rasterio dataset meta, faking an Earth CRS internally as needed."""
    with FakeEarthCOGReader(src_path, dataset=src_path) as cog:
        return get_cog_info(str(src_path), cog)
