"""Store run I/O in database."""

from ..types import (
    Calculation,
    CalculationGeometryLink,
    CalculationRow,
    Database,
    EnergyRow,
    Geometry,
    GeometryRow,
    Role,
    StationaryPointRow,
)


def calculation(db: Database, *, calc: Calculation | CalculationRow) -> CalculationRow:
    """Add a CalculationRow to the database."""
    calc = (
        calc
        if isinstance(calc, CalculationRow)
        else CalculationRow.from_calculation(calc)
    )
    return db.add(row=calc, eager_load=True)


def geometry(db: Database, *, geo: Geometry | GeometryRow) -> GeometryRow:
    """Store geometry in database."""
    geo = geo if isinstance(geo, GeometryRow) else GeometryRow.from_geometry(geo)
    return db.add(row=geo, eager_load=True)


def calc_geo_link(
    db: Database, *, calc: CalculationRow, geo: GeometryRow, role: Role
) -> CalculationGeometryLink:
    """
    Add a CalculationGeometryLink to the database.

    Parameters
    ----------
    db
        Database connection manager.
    calc
        CalculationRow to be linked.
    geo
        GeometryRow to be linked.

    Raises
    ------
    ValueError
        calc and/or geo are not assigned row ids.
    """
    if not calc.id or not geo.id:
        msg = f"Cannot link {calc = } with {geo = } without assigned row ids."
        raise ValueError(msg)

    link = CalculationGeometryLink(
        calculation_id=calc.id, geometry_id=geo.id, role=role
    )
    db.add(row=link, eager_load=True)

    return link


def energy(
    db: Database, *, calc: CalculationRow, geo: GeometryRow, value: float
) -> EnergyRow:
    """Store energy results in database."""
    ene_row = EnergyRow(
        calculation_id=calc.id,
        geometry_id=geo.id,
        value=value,
    )
    return db.add(row=ene_row, eager_load=True)


def stationary_point(
    db: Database,
    *,
    calc: CalculationRow,
    geo: GeometryRow,
    order: int,
    is_pseudo: bool = False,
) -> StationaryPointRow:
    """Store stationary point results in database."""
    if not calc.id or not geo.id:
        msg = f"Cannot link {calc = } with {geo = } without assigned row ids."
        raise ValueError(msg)

    stp_row = StationaryPointRow(
        geometry_id=geo.id, calculation_id=calc.id, order=order, is_pseudo=is_pseudo
    )

    return db.add(row=stp_row)
