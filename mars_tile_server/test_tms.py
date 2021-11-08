from morecantile import tms
import warnings
from morecantile.models import TileMatrixSet
from morecantile.commons import BoundingBox, Coords
from morecantile.errors import PointOutsideTMSBounds
from .crs import MARS2000_SPHERE, MARS_MERCATOR, mars_radius
from pydantic import PrivateAttr
from pyproj import Transformer
from morecantile.utils import (
    point_in_bbox,
    truncate_lnglat,
)

mercator_tms = tms.get("WebMercatorQuad")

pos_0 = (149.936, -3.752, 13)
pos_1 = (20, -80, 15)


class MarsTMS(TileMatrixSet):
    _to_mars2000 = PrivateAttr()
    _from_mars2000 = PrivateAttr()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Mars 2000 sphere can be used because lat/lon are defined
        # as planetocentric on Mars
        self._to_mars2000 = Transformer.from_crs(
            self.supportedCRS, MARS2000_SPHERE, always_xy=True
        )
        self._from_mars2000 = Transformer.from_crs(
            MARS2000_SPHERE, self.supportedCRS, always_xy=True
        )

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


def test_web_mercator_quad():
    tile = mercator_tms.tile(*pos_0)
    assert tile.z == pos_0[2]
    assert tile.x == 7507
    assert tile.y == 4181


def test_mars_projection():
    assert MARS2000_SPHERE.to_dict().get("R") == mars_radius
    assert MARS_MERCATOR.to_dict().get("R") == mars_radius


mars_tms = MarsTMS.custom(
    mercator_tms.bbox,
    MARS_MERCATOR,
    extent_crs=MARS2000_SPHERE,
    title="Web Mercator Mars",
)


def test_mars_tms():
    tile = mars_tms.tile(*pos_0)
    assert tile.z == pos_0[2]
    assert tile.x == 7507
    assert tile.y == 4181


def test_mars_tms_again():
    tile = mars_tms.tile(*pos_1)
    assert tile.z == pos_1[2]
    assert tile.x == 18204
    assert tile.y == 29089
