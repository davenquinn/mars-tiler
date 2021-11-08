import warnings
from pydantic import PrivateAttr
from pyproj import Transformer
from morecantile import tms
from morecantile.models import TileMatrixSet
from morecantile.commons import BoundingBox, Coords
from morecantile.errors import PointOutsideTMSBounds
from morecantile.utils import (
    point_in_bbox,
    truncate_lnglat,
)
from .crs import MARS2000_SPHERE, MARS_MERCATOR


def get_transform(*args):
    return Transformer.from_crs(*args, always_xy=True)


class MarsTMS(TileMatrixSet):
    _to_mars2000 = PrivateAttr()
    _from_mars2000 = PrivateAttr()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Mars 2000 sphere can be used because lat/lon are defined
        # as planetocentric on Mars
        self._to_mars2000 = get_transform(self.supportedCRS, MARS2000_SPHERE)
        self._from_mars2000 = get_transform(MARS2000_SPHERE, self.supportedCRS)

    @property
    def bbox(self):
        """Return TMS bounding box in WGS84."""
        bbox = self._to_mars2000.transform_bounds(*self.xy_bbox, densify_pts=21)
        return BoundingBox(*bbox)

    def xy(self, lng: float, lat: float, truncate=False) -> Coords:
        """Transform longitude and latitude coordinates to TMS CRS."""
        if truncate:
            lng, lat = truncate_lnglat(lng, lat)

        inside = point_in_bbox(Coords(lng, lat), self.bbox)
        if not inside:
            warnings.warn(
                f"Point ({lng}, {lat}) is outside TMS bounds {list(self.bbox)}.",
                PointOutsideTMSBounds,
            )

        x, y = self._from_mars2000.transform(lng, lat)

        return Coords(x, y)
