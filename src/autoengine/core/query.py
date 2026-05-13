"""Request existing models in database."""

from collections.abc import Iterator

from automol import Geometry
from autostorage import (
    CalculationRow,
    Database,
    EnergyRow,
    GeometryRow,
    Role,
    StationaryPointRow,
)


def calculations(
    db: Database, *, calc: CalculationRow, inp_geo: GeometryRow
) -> Iterator[CalculationRow]:
    """Yield matching calculation rows from database, if present."""
    if not inp_geo.id:
        msg = "inp_geo must have an id."
        raise ValueError(msg)

    for calc_row in db.find(row=calc, eager_load=True, exclude_id=True):
        if any(
            link.geometry_id == inp_geo.id and link.role == Role.input
            for link in getattr(calc_row, "geometry_links", [])
        ):
            yield calc_row


def geometry(db: Database, *, geo: Geometry | GeometryRow) -> Iterator[GeometryRow]:
    """Yield matching geometry row from database, if present."""
    geo = geo if isinstance(geo, GeometryRow) else GeometryRow.from_geometry(geo)
    yield from db.find(row=geo, eager_load=True, exclude_id=True)


def energies(
    db: Database, *, calc: CalculationRow, geo: GeometryRow
) -> Iterator[EnergyRow]:
    """Yield matching energy rows from database, if present."""
    for calc_row in calculations(db, calc=calc, inp_geo=geo):
        for ene_row in calc_row.energies:
            if ene_row.value:
                yield ene_row


def stationary_points(
    db: Database, *, calc: CalculationRow, geo: GeometryRow
) -> Iterator[StationaryPointRow]:
    """Yield matching energy rows from database, if present."""
    for calc_row in calculations(db, calc=calc, inp_geo=geo):
        for stp_row in calc_row.stationary_points:
            if stp_row.id:
                yield stp_row
