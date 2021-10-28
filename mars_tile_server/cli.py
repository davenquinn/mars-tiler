import os
import sys
import click

from rich import print
from cogeo_mosaic.utils import _filter_futures
from cogeo_mosaic.mosaic import MosaicJSON
from cogeo_mosaic.backends import MosaicBackend
import typer
from typing import Sequence, List, Optional
from pathlib import Path
from concurrent import futures
import warnings

from .util import get_dataset_info

cli = typer.Typer()


def get_footprints(
    dataset_list: Sequence[Path], max_threads: int = 20, quiet: bool = True, **kwargs
) -> List:
    """
    Create footprint GeoJSON.
    Attributes
    ----------
    dataset_listurl : tuple or list, required
        Dataset urls.
    max_threads : int
        Max threads to use (default: 20).
    Returns
    -------
    out : tuple
        tuple of footprint feature.
    """
    fout = os.devnull if quiet else sys.stderr
    with futures.ThreadPoolExecutor(max_workers=max_threads) as executor:
        future_work = [
            executor.submit(lambda x: get_dataset_info(x, **kwargs), item)
            for item in dataset_list
        ]
        with click.progressbar(  # type: ignore
            futures.as_completed(future_work),
            file=fout,
            length=len(future_work),
            label="Get footprints",
            show_percent=True,
        ) as future:
            for _ in future:
                pass

    return list(_filter_futures(future_work))


def ensure_absolute_paths(*paths: Path):
    for path in paths:
        if not path.is_absolute():
            yield Path("/mars-data") / path
        else:
            yield path


@cli.command(name="create-mosaic")
def create_mosaic(
    output: Path,
    files: Optional[List[Path]] = [],
    quiet: bool = False,
    file_list: Optional[Path] = None,
    dry_run: bool = None,
    dtype: str = None,
):
    if file_list is not None:
        files = [Path(f.strip()) for f in file_list.open().readlines()]

    files = ensure_absolute_paths(*files)

    features = get_footprints(files, quiet=quiet, dtype=dtype)

    if dry_run:
        for f in features:
            print(f)
        return

    minzoom = None
    maxzoom = 8

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

    datatype = {feat["properties"]["datatype"] for feat in features}
    if len(datatype) > 1:
        print(datatype)
        raise Exception("Datasets should have the same data type")

    mosaic = MosaicJSON._create_mosaic(
        features, minzoom=minzoom, maxzoom=maxzoom, quiet=quiet, minimum_tile_cover=0.25
    )

    with MosaicBackend(str(output), mosaic_def=mosaic) as mosaic:
        mosaic.write(overwrite=True)
