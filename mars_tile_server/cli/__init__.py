from typer import Typer
from typing import List
from pathlib import Path
from rich import print
from macrostrat.core_utils import relative_path

from ..database import db
from .mosaic import mosaic_cli, get_footprints

cli = Typer()

cli.add_typer(mosaic_cli, name="create-mosaic")


@cli.command(name="create-tables")
def create_tables():
    dn = Path(relative_path(__file__, "../../sql"))
    for file in dn.glob("*.sql"):
        db.exec_sql(file)


@cli.command(name="update-footprints")
def update_footprints(mosaic: str, datasets: List[Path]):
    footprints = get_footprints(datasets)
    for footprint in footprints:
        print(footprint)
