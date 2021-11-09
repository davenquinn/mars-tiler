from pathlib import Path
from sparrow.utils import relative_path
from shapely.geometry import Polygon, shape
from .util import get_dataset_info
from .defs import mars_tms

fixtures = Path(relative_path(__file__, "..", "test-fixtures")).resolve()


def dataset_footprint(image: Path):
    info = get_dataset_info(image)
    return shape(info["geometry"])


def _tile_geom(tile):
    feat = mars_tms.feature(tile)
    return shape(feat["geometry"])
