import warnings
from pydantic import PrivateAttr
from pyproj import Transformer
from typing import Dict, Optional, Any
from morecantile import tms
from morecantile.models import Tile, TileMatrixSet, NumType, BoundingBox, Coords
from morecantile.errors import PointOutsideTMSBounds
from morecantile.utils import point_in_bbox, truncate_lnglat, bbox_to_feature
from .crs import MARS2000_SPHERE, MARS_MERCATOR


def get_transform(*args):
    return Transformer.from_crs(*args, always_xy=True)


def warn_if_outside(x: float, y: float, bbox: BoundingBox):
    if point_in_bbox(Coords(x, y), bbox):
        return
    warnings.warn(
        f"Point ({x}, {y}) is outside TMS bounds {list(bbox)}.",
        PointOutsideTMSBounds,
    )


class MarsTMS(TileMatrixSet):
    _to_mars2000 = PrivateAttr()
    _from_mars2000 = PrivateAttr()
    _to_wgs84 = PrivateAttr()
    _from_wgs84 = PrivateAttr()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Mars 2000 sphere can be used because lat/lon are defined
        # as planetocentric on Mars
        self._to_mars2000 = get_transform(self.supportedCRS, MARS2000_SPHERE)
        self._to_wgs84 = self._to_mars2000
        self._from_mars2000 = get_transform(MARS2000_SPHERE, self.supportedCRS)
        self._from_wgs84 = self._from_mars2000

    @property
    def bbox(self):
        """Return TMS bounding box in WGS84."""
        bbox = self._to_mars2000.transform_bounds(*self.xy_bbox, densify_pts=21)
        return BoundingBox(*bbox)

    def xy(self, lng: float, lat: float, truncate=False) -> Coords:
        """Transform longitude and latitude coordinates to TMS CRS."""
        if truncate:
            lng, lat = truncate_lnglat(lng, lat)

        warn_if_outside(lng, lat, self.bbox)

        x, y = self._from_mars2000.transform(lng, lat)

        return Coords(x, y)

    def lnglat(self, x: float, y: float, truncate=False) -> Coords:
        """Transform point(x,y) to longitude and latitude."""
        warn_if_outside(x, y, self.xy_bbox)
        lng, lat = self._to_mars2000.transform(x, y)

        if truncate:
            lng, lat = truncate_lnglat(lng, lat)

        return Coords(lng, lat)

    def feature(
        self,
        tile: Tile,
        fid: Optional[str] = None,
        props: Dict = {},
        buffer: Optional[NumType] = None,
        precision: Optional[int] = None,
        projected: bool = False,
    ) -> Dict:
        west, south, east, north = self.xy_bounds(tile)

        if not projected:
            west, south, east, north = self._to_mars2000.transform_bounds(
                west, south, east, north, densify_pts=21
            )

        if buffer:
            west -= buffer
            south -= buffer
            east += buffer
            north += buffer

        if precision and precision >= 0:
            west, south, east, north = (
                round(v, precision) for v in (west, south, east, north)
            )

        bbox = [min(west, east), min(south, north), max(west, east), max(south, north)]
        geom = bbox_to_feature(west, south, east, north)

        xyz = str(tile)
        feat: Dict[str, Any] = {
            "type": "Feature",
            "bbox": bbox,
            "id": xyz,
            "geometry": geom,
            "properties": {
                "title": f"XYZ tile {xyz}",
                "grid_name": self.identifier,
                "grid_crs": self.crs.to_string(),
            },
        }

        if projected:
            warnings.warn(
                "CRS is no longer part of the GeoJSON specification."
                "Other projection than EPSG:4326 might not be supported.",
                UserWarning,
            )
            feat.update(
                {"crs": {"type": "EPSG", "properties": {"code": self.crs.to_epsg()}}}
            )

        if props:
            feat["properties"].update(props)

        if fid is not None:
            feat["id"] = fid

        return feat
