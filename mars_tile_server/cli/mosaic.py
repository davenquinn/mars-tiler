import os
import sys
import click
from typer import Typer

from rich import print
from cogeo_mosaic.utils import _filter_futures
from cogeo_mosaic.mosaic import MosaicJSON
from cogeo_mosaic.backends import MosaicBackend
from typing import Sequence, List, Optional
from pathlib import Path
from concurrent import futures
import warnings

from sparrow.utils import get_logger
from ..util import get_dataset_info

log = get_logger()

mosaic_cli = Typer()


def get_footprints(dataset_list: Sequence[Path], **kwargs) -> List:
    for item in dataset_list:
        yield get_dataset_info(item, **kwargs)


def ensure_absolute_paths(*paths: Path):
    for path in paths:
        if not path.is_absolute():
            yield Path("/mars-data") / path
        else:
            yield path


@mosaic_cli.command(name="create-mosaic")
def create_mosaic(
    output: Path,
    files: Optional[List[Path]] = [],
    quiet: bool = False,
    file_list: Optional[Path] = None,
    dry_run: bool = None,
    dtype: str = None,
    quadkey_zoom: int = None,
):
    if file_list is not None:
        files = [
            Path(f.strip())
            for f in file_list.open().readlines()
            if not f.startswith("#")
        ]

    files = ensure_absolute_paths(*files)
    files = list(files)
    files.reverse()
    for f in files:
        print(str(f))

    features = get_footprints(files, quiet=quiet, dtype=dtype)

    if dry_run:
        for f in features:
            print(f)
        return

    minzoom = None
    maxzoom = None

    if minzoom is None:
        data_minzoom = {feat["properties"]["minzoom"] for feat in features}
        if len(data_minzoom) > 1:
            warnings.warn(
                "Multiple MinZoom, Assets different minzoom values", UserWarning
            )

        minzoom = min(data_minzoom)

    if maxzoom is None:
        data_maxzoom = {feat["properties"]["maxzoom"] for feat in features}
        if len(data_maxzoom) > 1:
            warnings.warn(
                "Multiple MaxZoom, Assets have multiple resolution values",
                UserWarning,
            )

        maxzoom = max(data_maxzoom)

    if quadkey_zoom is None:
        quadkey_zoom = maxzoom

    print(f"Getting data in zoom range {minzoom}, {maxzoom}")

    datatype = {feat["properties"]["datatype"] for feat in features}
    if len(datatype) > 1:
        print(datatype)
        raise Exception("Datasets should have the same data type")

    mosaic = MosaicJSON._create_mosaic(
        features,
        minzoom=minzoom,
        maxzoom=maxzoom,
        quiet=quiet,
        quadkey_zoom=quadkey_zoom,
    )

    with MosaicBackend(str(output), mosaic_def=mosaic) as mosaic:
        mosaic.write(overwrite=True)
