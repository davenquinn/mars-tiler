import json
import multiprocessing
import os

import click
import cligj
import mercantile
from click_plugins import with_plugins
from pkg_resources import iter_entry_points

from cogeo_mosaic import __version__ as cogeo_mosaic_version
from cogeo_mosaic.backends import MosaicBackend
from cogeo_mosaic.mosaic import MosaicJSON
from cogeo_mosaic.utils import get_footprints


def cli():
    input_files = [file.strip() for file in input_files if file.strip()]
    mosaicjson = MosaicJSON.from_urls(
        input_files,
        minzoom=minzoom,
        maxzoom=maxzoom,
        quadkey_zoom=quadkey_zoom,
        minimum_tile_cover=min_tile_cover,
        tile_cover_sort=tile_cover_sort,
        max_threads=threads,
        quiet=quiet,
    )

    if name:
        mosaicjson.name = name
    if description:
        mosaicjson.description = description
    if attribution:
        mosaicjson.attribution = attribution

    if output:
        with MosaicBackend(output, mosaic_def=mosaicjson) as mosaic:
            mosaic.write(overwrite=True)
    else:
        click.echo(mosaicjson.json(exclude_none=True))


if __name__ == "__main__":
    cli()
