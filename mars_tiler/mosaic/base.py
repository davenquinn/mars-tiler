"""Mosaic definitions (a close approximation of Cogeo-Mosaic BaseBackend)"""

import attr
from typing import Any, Dict, List, Tuple, Type, Optional
from morecantile import TileMatrixSet, Tile
from rasterio.crs import CRS
from rio_tiler.constants import WEB_MERCATOR_TMS
from rio_tiler.errors import PointOutsideBounds
from rio_tiler.io import BaseReader, COGReader
from rio_tiler.models import ImageData
from rio_tiler.mosaic import mosaic_reader
from rio_tiler.tasks import multi_values
from cogeo_mosaic.errors import NoAssetFoundError
from sparrow.utils import get_logger
from mercantile import bounds
from pydantic import BaseModel

from ..timer import Timer
from ..database import get_sync_database, prepared_statement
from ..util import dataset_path
from ..database import get_sync_database, prepared_statement, get_database

log = get_logger(__name__)


class OverscaledAssetsError(NoAssetFoundError):
    ...


class MosaicAsset(BaseModel):
    path: str
    mosaic: Optional[str]
    rescale_range: Optional[List[float]]
    minzoom: int
    maxzoom: int
    overscaled: bool


def create_asset(d):
    row = dict(d)
    return MosaicAsset(
        path=get_path(row["path"]),
        mosaic=str(row["mosaic"]),
        rescale_range=row.get("rescale_range", None),
        minzoom=int(row["minzoom"]),
        maxzoom=int(row["maxzoom"]),
        overscaled=bool(row["overscaled"]),
    )


def get_path(d: str):
    value = str(d)
    prefix = "/mars-data"
    if value.startswith(prefix):
        return dataset_path(str(value[len(prefix) :]))
    return value


def get_datasets(tile, mosaics: List[str]) -> List[MosaicAsset]:
    Timer.add_step("tilebounds")
    db = get_sync_database()
    Timer.add_step("dbconnect")
    res = db.session.execute(
        "SELECT (imagery.get_datasets(:x, :y, :z, :mosaics)).*",
        dict(x=tile.x, y=tile.y, z=tile.z, mosaics=mosaics),
    )
    Timer.add_step("findassets")

    return [create_asset(d) for d in res if int(d._mapping["minzoom"]) - 5 < tile.z]


def rescale_postprocessor(asset: MosaicAsset):
    rng = asset.rescale_range

    def processor(data, mask):
        if rng is not None:
            data = ((data - rng[0]) * (1 / (rng[1] - rng[0]) * 255)).astype("uint8")
        return data, mask

    return processor


@attr.s
class PGMosaicBackend(BaseReader):
    """Base Class for cogeo-mosaic backend storage, modified for async use
    Original file is `cogeo_mosaic.backends.base`

    Attributes:
        input (str): mosaic path.
        reader (rio_tiler.io.BaseReader): Dataset reader. Defaults to `rio_tiler.io.COGReader`.
        reader_options (dict): Options to forward to the reader config.
        tms (morecantile.TileMatrixSet, optional): TileMatrixSet grid definition. **READ ONLY attribute**. Defaults to `WebMercatorQuad`.
        bbox (tuple): mosaic bounds (left, bottom, right, top). **READ ONLY attribute**. Defaults to `(-180, -90, 180, 90)`.
        minzoom (int): mosaic Min zoom level. **READ ONLY attribute**. Defaults to `0`.
        maxzoom (int): mosaic Max zoom level. **READ ONLY attribute**. Defaults to `30`

    """

    reader: Type[BaseReader] = attr.ib(default=COGReader)
    reader_options: Dict = attr.ib(factory=dict)
    quadkey_zoom: int = attr.ib(default=10)

    # TMS is outside the init because mosaicJSON and cogeo-mosaic only
    # works with WebMercator (mercantile) for now.
    tms: TileMatrixSet = attr.ib(init=False, default=WEB_MERCATOR_TMS)
    minzoom: int = attr.ib(init=False)
    maxzoom: int = attr.ib(init=False)

    # default values for bounds
    bounds: Tuple[float, float, float, float] = attr.ib(
        init=False, default=(-180, -90, 180, 90)
    )
    crs: CRS = attr.ib(init=False, default=CRS.from_epsg(4326))

    def assets_for_tile(
        self, x: int, y: int, z: int, allow_overscaled=False
    ) -> List[MosaicAsset]:
        """Retrieve assets for tile."""
        mosaic_assets = self.get_assets(x, y, z)

        # If all assets are overscaled, we return nothing.
        overscaled_assets = [a for a in mosaic_assets if z > a.maxzoom]
        all_overscaled = len(overscaled_assets) == len(mosaic_assets)
        if all_overscaled and not allow_overscaled:
            raise OverscaledAssetsError("All available assets are overscaled")

        return mosaic_assets

    def assets_for_point(self, lng: float, lat: float) -> List[MosaicAsset]:
        """Retrieve assets for point."""
        tile = self.tms.tile(lng, lat, self.quadkey_zoom)
        return self.get_assets(tile.x, tile.y, tile.z)

    def get_assets(self, x: int, y: int, z: int) -> List[MosaicAsset]:
        return get_datasets(Tile(x, y, z), self.input)

    def _reader(self, asset: MosaicAsset):
        """Diverging from cogeo-mosaic, we define the reader at the class level."""
        return self.reader(
            asset.path, post_process=rescale_postprocessor(asset), **self.reader_options
        )

    def tile(  # type: ignore
        self,
        x: int,
        y: int,
        z: int,
        reverse: bool = False,
        assets: Optional[List[MosaicAsset]] = None,
        **kwargs: Any,
    ) -> Tuple[ImageData, List[object]]:
        """Get Tile from multiple observation."""
        if assets is None:
            assets = self.assets_for_tile(x, y, z)
        if not assets:
            raise NoAssetFoundError(f"No assets found for tile {z}-{x}-{y}")

        if reverse:
            assets = list(reversed(assets))

        def _reader(
            asset: MosaicAsset, x: int, y: int, z: int, **kwargs: Any
        ) -> ImageData:
            with self._reader(asset) as src_dst:
                return src_dst.tile(x, y, z, **kwargs)

        data = mosaic_reader(assets, _reader, x, y, z, **kwargs)
        Timer.add_step("readdata")
        return data

    def point(
        self,
        lon: float,
        lat: float,
        reverse: bool = False,
        **kwargs: Any,
    ) -> List:
        """Get Point value from multiple observation."""
        mosaic_assets = self.assets_for_point(lon, lat)
        if not mosaic_assets:
            raise NoAssetFoundError(f"No assets found for point ({lon},{lat})")

        if reverse:
            mosaic_assets = list(reversed(mosaic_assets))

        def _reader(asset: MosaicAsset, lon: float, lat: float, **kwargs) -> Dict:
            with self._reader(asset) as src_dst:
                return src_dst.point(lon, lat, **kwargs)

        if "allowed_exceptions" not in kwargs:
            kwargs.update({"allowed_exceptions": (PointOutsideBounds,)})

        return list(multi_values(mosaic_assets, _reader, lon, lat, **kwargs).items())

    def info(self):
        raise NotImplementedError

    def stats(self):
        raise NotImplementedError

    def statistics(self):
        """PlaceHolder for BaseReader.statistics."""
        raise NotImplementedError

    def preview(self):
        """PlaceHolder for BaseReader.preview."""
        raise NotImplementedError

    def part(self):
        """PlaceHolder for BaseReader.part."""
        raise NotImplementedError

    def feature(self):
        """PlaceHolder for BaseReader.feature."""
        raise NotImplementedError
