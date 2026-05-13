"""Higher-level run calls."""

from collections.abc import Iterator
from pathlib import Path

from ..qc import program_output, structure
from ..types import (
    CalcType,
    Calculation,
    Database,
    EnergyRow,
    Geometry,
    Role,
    StationaryPointRow,
)
from . import query, store, utils


def energy(
    db_uri: str | Path, *, calc: Calculation, geo: Geometry
) -> Iterator[EnergyRow]:
    """Run an energy calculation."""
    db = Database(db_uri)
    inp_calc, inp_geo = utils.prepare_inputs(
        db, calc=calc, geo=geo, calc_type=CalcType.energy
    )

    ene_rows = list(query.energies(db, calc=inp_calc, geo=inp_geo))
    if ene_rows:
        yield from ene_rows
        return

    prog_out = utils.run_calculation(inp_calc=inp_calc, inp_geo=inp_geo)

    out_calc = program_output.calculation(prog_out=prog_out)
    store.calculation(db, calc=out_calc)
    store.calc_geo_link(db, calc=out_calc, geo=inp_geo, role=Role.input)

    yield store.energy(db, calc=out_calc, geo=inp_geo, value=prog_out.data.energy)


def initial_geometry(
    db: Database, *, calc: Calculation, geo: Geometry, order: int = 0
) -> Iterator[StationaryPointRow]:
    """Run a geometry optimization."""
    inp_calc, inp_geo = utils.prepare_inputs(
        db, calc=calc, geo=geo, calc_type=CalcType.optimization
    )

    stp_rows = list(query.stationary_points(db, calc=inp_calc, geo=inp_geo))
    if stp_rows:
        yield from stp_rows
        return

    prog_out = utils.run_calculation(inp_calc=inp_calc, inp_geo=inp_geo)

    out_calc = program_output.calculation(prog_out=prog_out)
    store.calculation(db, calc=out_calc)
    store.calc_geo_link(db, calc=out_calc, geo=inp_geo, role=Role.input)

    out_geo = structure.geometry(prog_out.data.final_structure)
    store.geometry(db, geo=out_geo)
    store.calc_geo_link(db, calc=out_calc, geo=out_geo, role=Role.output)

    store.energy(db, calc=out_calc, geo=out_geo, value=prog_out.data.final_energy)
    yield store.stationary_point(db, calc=out_calc, geo=out_geo, order=order)
