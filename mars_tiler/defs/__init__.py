from morecantile import tms
from morecantile.models import TileMatrixSet
from .crs import MARS2000_SPHERE, MARS_MERCATOR, MARS2000, mars_mercator_wkt, MARS_EQC

mercator_tms = tms.get("WebMercatorQuad")

import rasterio


class MarsCRS(rasterio.crs.CRS):
    def to_epsg(self):
        return None

    def to_authority(self):
        return "IAU"


class MarsTMS(TileMatrixSet):
    ...

    @property
    def rasterio_crs(self):
        """Return rasterio CRS."""

        return MarsCRS.from_wkt(self.crs.to_wkt())


mars_tms = MarsTMS.custom(
    mercator_tms.bbox,
    MARS_MERCATOR,
    extent_crs=MARS2000_SPHERE,
    title="Web Mercator Mars",
    geographic_crs=MARS2000_SPHERE,
    minzoom=0,
    maxzoom=24,
)
