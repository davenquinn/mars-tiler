from typer import Typer
from typing import List, Optional
from pathlib import Path
from rich import print
from time import sleep

from geoalchemy2.shape import from_shape
from shapely.geometry import shape
from sparrow.utils import relative_path
from sparrow.dinosaur import Dinosaur

from ..database import db
from .mosaic import mosaic_cli, get_footprints

import logging
import sys

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

cli = Typer()

cli.add_typer(mosaic_cli, name="create-mosaic")


def initialize_database(db):
    dn = Path(relative_path(__file__, "../../sql"))
    for file in dn.glob("*.sql"):
        db.exec_sql(file)


@cli.command(name="create-tables")
def create_tables():
    initialize_database()


@cli.command(name="update-footprints")
def update_footprints(
    datasets: List[Path], mosaic: Optional[str] = None, update: bool = False
):
    db.automap()
    # We seem to have to remap public for changes to take hold...
    db.mapper.reflect_schema("public")
    db.mapper.reflect_schema("imagery")
    db.mapper.reflect_schema("public")

    Dataset = db.model.imagery_dataset

    _datasets = datasets
    if not update:
        ds_ids = db.session.query(Dataset.name).all()
        _datasets = (d for d in datasets if d.stem not in ds_ids)

    footprints = get_footprints(_datasets)
    for f in footprints:

        path = Path(f["properties"]["path"]).absolute()

        dataset = Dataset(
            footprint=from_shape(shape(f["geometry"])),
            path=str(path),
            name=path.stem,
            minzoom=f["properties"]["minzoom"],
            maxzoom=f["properties"]["maxzoom"],
            dtype=f["properties"]["datatype"],
            mosaic=mosaic,
        )
        db.session.add(dataset)
        db.session.commit()


_base = "postgresql://postgres:angry0405wombat@database:5432/"


class Migrator(Dinosaur):
    target_url = _base + "footprints_temp_migration"
    dry_run_url = _base + "footprints_schema_clone"


@cli.command(name="migrate")
def migrate(force: bool = False):
    kwargs = dict(dry_run=False, apply=False)
    if force:
        kwargs["apply"] = True

    migrator = Migrator(db, initialize_database, migrations=[])
    migrator.run_migration(**kwargs)
