from typer import Typer
from typing import List, Optional
from pathlib import Path
from rich import print

from sparrow.utils import relative_path
from sparrow.dinosaur import update_schema

from ..database import db
from .mosaic import mosaic_cli, get_footprints

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
def update_footprints(datasets: List[Path], mosaic: Optional[str] = None):
    footprints = get_footprints(datasets)
    for footprint in footprints:
        print(footprint)


@cli.command(name="migrate")
def migrate(force: bool = False):
    kwargs = dict(dry_run=True, apply=False)
    if force:
        kwargs = dict(dry_run=False, apply=True)

    update_schema(db, initialize_database, migrations=[], **kwargs)
