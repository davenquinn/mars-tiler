import json
import os
import sys
import click

# import click
# import cligj
# import mercantile
# from click_plugins import with_plugins
# from pkg_resources import iter_entry_points

# from cogeo_mosaic import __version__ as cogeo_mosaic_version
# from cogeo_mosaic.backends import MosaicBackend
# from cogeo_mosaic.mosaic import MosaicJSON
from cogeo_mosaic.utils import _filter_futures
from rio_tiler.io import COGReader
from rasterio.vrt import WarpedVRT
from rasterio.crs import CRS
import rasterio
import typer
from typing import Sequence, Dict, List
from pathlib import Path
from rich import print
from concurrent import futures

cli = typer.Typer()


def get_cog_info(src_path: str, cog: COGReader):
    bounds = cog.bounds
    return {
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [bounds[0], bounds[3]],
                    [bounds[0], bounds[1]],
                    [bounds[2], bounds[1]],
                    [bounds[2], bounds[3]],
                    [bounds[0], bounds[3]],
                ]
            ],
        },
        "properties": {
            "path": src_path,
            "bounds": cog.bounds,
            "minzoom": cog.minzoom,
            "maxzoom": cog.maxzoom,
            "datatype": cog.dataset.meta["dtype"],
        },
        "type": "Feature",
    }


EARTH_RADIUS = 6378137


def fake_earth_crs(crs: CRS) -> CRS:
    data = crs.to_dict()
    radius = data.get("R", None)
    if radius is None:
        raise AttributeError(
            "Error faking Earth CRS: Input does not have 'R' parameter..."
        )
    if radius == EARTH_RADIUS:
        return crs
    data["R"] = EARTH_RADIUS
    return CRS.from_dict(data)


def get_dataset_info(src_path: str) -> Dict:
    """Get rasterio dataset meta, faking an Earth CRS internally as needed."""
    with rasterio.open(src_path) as src_dst:
        with WarpedVRT(
            src_dst,
            # Fake an Earth radius.
            src_crs=fake_earth_crs(src_dst.crs),
        ) as vrt_dst:
            with COGReader(None, dataset=vrt_dst) as cog:
                return get_cog_info(str(src_path), cog)


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
def create_mosaic(files: List[Path]):
    footprints = get_footprints(files, quiet=False)
    print(footprints)


# def create_mosaic(input_files):
#     input_files = [file.strip() for file in input_files if file.strip()]
#     mosaicjson = MosaicJSON.from_urls(
#         input_files,
#         minzoom=minzoom,
#         maxzoom=maxzoom,
#         quadkey_zoom=quadkey_zoom,
#         minimum_tile_cover=min_tile_cover,
#         tile_cover_sort=tile_cover_sort,
#         max_threads=threads,
#         quiet=quiet,
#     )

#     if name:
#         mosaicjson.name = name
#     if description:
#         mosaicjson.description = description
#     if attribution:
#         mosaicjson.attribution = attribution

#     if output:
#         with MosaicBackend(output, mosaic_def=mosaicjson) as mosaic:
#             mosaic.write(overwrite=True)
#     else:
#         click.echo(mosaicjson.json(exclude_none=True))
