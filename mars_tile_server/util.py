from typing import Dict
from rio_tiler.io import COGReader
from rasterio.vrt import WarpedVRT
from rasterio.crs import CRS
from rio_rgbify.encoders import data_to_rgb
import rasterio
import logging

log = logging.getLogger(__name__)


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
        dtype = kwargs.pop("dtype", None)
        dataset = WarpedVRT(
            self.src_dst, src_crs=fake_earth_crs(self.src_dst.crs), dtype=dtype
        )
        super().__init__(None, dataset, *args, **kwargs)

    def close(self):
        self.src_dst.close()
        super().close()


def post_process(elevation, mask):
    rgb = data_to_rgb(elevation[0], -10000, 0.1)
    return rgb, mask


# Can't figure out why subclassing doesn't work properly for COGReader...
class ElevationReader(FakeEarthCOGReader):
    def preview(self, *args, **kwargs):
        kwargs["post_process"] = post_process
        return super().preview(*args, **kwargs)

    def part(self, *args, **kwargs):
        kwargs["post_process"] = post_process
        return super().part(*args, **kwargs)


def get_cog_info(src_path: str, cog: COGReader):
    bounds = cog.bounds
    print(bounds)
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


def get_dataset_info(src_path: str, **kwargs) -> Dict:
    """Get rasterio dataset meta, faking an Earth CRS internally as needed."""
    with COGReader(src_path, **kwargs) as cog:
        return get_cog_info(str(src_path), cog)
