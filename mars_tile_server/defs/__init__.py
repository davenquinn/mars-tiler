from morecantile import tms
from morecantile.models import TileMatrixSet
from .crs import MARS2000_SPHERE, MARS_MERCATOR

mercator_tms = tms.get("WebMercatorQuad")
mars_tms = TileMatrixSet.custom(
    mercator_tms.bbox,
    MARS_MERCATOR,
    extent_crs=MARS2000_SPHERE,
    title="Web Mercator Mars",
    geographic_crs=MARS2000_SPHERE,
)
