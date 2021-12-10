from typer import Typer, Argument, Context
from typing import List, Optional
from pathlib import Path
from rich import print
from time import sleep
from os import environ
from json import loads
from dataclasses import dataclass

from geoalchemy2.shape import from_shape
from shapely.geometry import shape
from sparrow.utils import relative_path, cmd
from sparrow.dinosaur import Dinosaur

from ..database import get_sync_database
from .mosaic import mosaic_cli, get_footprints

import rasterio
import logging
import sys

# logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

cli = Typer()

cli.add_typer(mosaic_cli, name="create-mosaic")


def initialize_database(db):
    dn = Path(relative_path(__file__, "../../sql"))
    for file in dn.glob("*.sql"):
        db.exec_sql(file)


@cli.command(name="create-tables")
def create_tables():
    initialize_database()


images = Typer(no_args_is_help=True)
cli.add_typer(images, name="images")

@dataclass
class CommandContext:
    search: str = None
    mosaic: str = None
    @property
    def datasets(self):
        return get_datasets(search_string=self.search, mosaic=self.mosaic)


@images.callback()
def images_main(ctx: Context, search: str = None, mosaic: str = None):
    """
    Manage images.
    """
    ctx.obj = CommandContext(search, mosaic)

def get_json_info(dataset: Path):
    output = cmd("gdalinfo -json -approx_stats", str(dataset), capture_output=True)
    return loads(output.stdout)

def _update_info(datasets, mosaic=None):
    db = get_sync_database()
    Dataset = db.model.imagery_dataset
    footprints = get_footprints(datasets)
    for f in footprints:
        path = Path(f["properties"]["path"]).absolute()

        kw = dict(
            footprint=from_shape(shape(f["geometry"]), 949900),
            path=str(path),
            minzoom=f["properties"]["minzoom"],
            maxzoom=f["properties"]["maxzoom"],
            dtype=f["properties"]["datatype"],
        )

        if mosaic is not None:
            kw["mosaic"] = mosaic

        dataset = db.get_or_create(Dataset, name=path.stem)
        for k, v in kw.items():
            setattr(dataset, k, v)
        db.session.add(dataset)
        db.session.commit()


@images.command(name="add")
def add_footprints(datasets: List[Path], mosaic: Optional[str] = None):
    _update_info(datasets, mosaic)


def get_datasets(*, search_string: str = None, mosaic=None):
    db = get_sync_database()
    Dataset = db.model.imagery_dataset
    datasets = db.session.query(Dataset)
    if mosaic is not None:
        datasets = datasets.filter(Dataset.mosaic == mosaic)
    if search_string is not None:
        datasets = datasets.filter(Dataset.name.contains(search_string))
    return (Path(d.path) for d in datasets)


@cli.command(name="update")
def update_info(ctx: Context):
    obj = ctx.find_object(CommandContext)
    _update_info(obj.datasets, mosaic=obj.mosaic)


@images.command(name="info")
def get_info(ctx: Context, full: bool = False):
    obj = ctx.find_object(CommandContext)
    for dataset in obj.datasets:
        with rasterio.open(dataset) as ds:
            print(str(dataset.name))
            print(ds.nodata)
            print(f"[dim]{ds.crs}")
            if full:
                print(get_json_info(dataset))
            print()

@images.command(name="paths")
def paths(ctx: Context, full: bool = False):
    obj = ctx.find_object(CommandContext)

    public_url = environ.get("PUBLIC_URL")
    mars_data = environ.get("MARS_DATA_DIR")
    for dataset in obj.datasets:
        with rasterio.open(dataset) as ds:
            fp = str(dataset)
            if full:
                fp = fp.replace(mars_data, public_url)
            print(fp)


@images.command(name="add-nodata")
def add_nodata(ctx: Context, value: int):
    ctx.find_object(CommandContext)
    for dataset in ctx.datasets:
        with rasterio.open(dataset, "r+") as ds:
            print(str(dataset.name))
            if ds.nodata is not None:
                print("[dim]Nodata value already set")
                continue
            ds.nodata = value


_base = "postgresql://postgres:angry0405wombat@database:5432/"


class Migrator(Dinosaur):
    target_url = _base + "footprints_temp_migration"
    dry_run_url = _base + "footprints_schema_clone"


@cli.command(name="migrate")
def migrate(force: bool = False):
    db = get_sync_database()
    kwargs = dict(dry_run=False, apply=False)
    if force:
        kwargs["apply"] = True

    migrator = Migrator(db, initialize_database, migrations=[])
    migrator.run_migration(**kwargs)
