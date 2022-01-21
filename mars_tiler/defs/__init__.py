from morecantile import tms
from morecantile.models import TileMatrixSet
from .crs import MARS2000_SPHERE, MARS_MERCATOR, MARS2000, mars_mercator_wkt, MARS_EQC
import rasterio

mercator_tms = tms.get("WebMercatorQuad")

# monkey-patch rasterio to use Mars projections

_CRS_OLD = rasterio.crs.CRS


class MarsCRS(_CRS_OLD):
    def to_epsg(self):
        return None

    def to_authority(self):
        return None


rasterio.crs.CRS = MarsCRS


class MarsTMS(TileMatrixSet):
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
