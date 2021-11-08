from morecantile import tms
from .crs import MARS2000_SPHERE, MARS_MERCATOR
from .base import MarsTMS

mercator_tms = tms.get("WebMercatorQuad")
mars_tms = MarsTMS.custom(
    mercator_tms.bbox,
    MARS_MERCATOR,
    extent_crs=MARS2000_SPHERE,
    title="Web Mercator Mars",
)
