import os
import sys
import click

from cogeo_mosaic.utils import _filter_futures
from cogeo_mosaic.mosaic import MosaicJSON
from cogeo_mosaic.backends import MosaicBackend
import typer
from typing import Sequence, List
from pathlib import Path
from concurrent import futures
import warnings

from .util import get_dataset_info

cli = typer.Typer()


def get_footprints(
    dataset_list: Sequence[Path], max_threads: int = 20, quiet: bool = True
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
        future_work = [executor.submit(get_dataset_info, item) for item in dataset_list]
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


@cli.command()
def create_mosaic(files: List[Path], output: Path, quiet: bool = False):
    features = get_footprints(files, quiet=quiet)

    minzoom = None
    maxzoom = 8

    if minzoom is None:
        data_minzoom = {feat["properties"]["minzoom"] for feat in features}
        if len(data_minzoom) > 1:
            warnings.warn(
                "Multiple MinZoom, Assets different minzoom values", UserWarning
            )

        minzoom = max(data_minzoom)

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
        raise Exception("Dataset should have the same data type")

    mosaic = MosaicJSON._create_mosaic(
        features, minzoom=minzoom, maxzoom=maxzoom, quiet=quiet, minimum_tile_cover=0.2
    )

    with MosaicBackend(str(output), mosaic_def=mosaic) as mosaic:
        mosaic.write(overwrite=True)
