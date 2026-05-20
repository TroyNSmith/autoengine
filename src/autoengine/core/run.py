"""Higher-level run calls."""

from collections.abc import Iterator

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


def energy(db: Database, *, calc: Calculation, geo: Geometry) -> Iterator[EnergyRow]:
    """Run an energy calculation."""
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


def conformer_search(
    db: Database, *, calc: Calculation, geo: Geometry, order: int = 0
) -> Iterator[StationaryPointRow]:
    """Run a conformer search."""
    inp_calc, inp_geo = utils.prepare_inputs(
        db, calc=calc, geo=geo, calc_type=CalcType.conformer_search
    )

    stp_rows = list(query.stationary_points(db, calc=inp_calc, geo=inp_geo))
    if stp_rows:
        yield from stp_rows
        return

    prog_out = utils.run_calculation(inp_calc=inp_calc, inp_geo=inp_geo)

    out_calc = program_output.calculation(prog_out=prog_out)
    store.calculation(db, calc=out_calc)
    store.calc_geo_link(db, calc=out_calc, geo=inp_geo, role=Role.input)

    for struct, energy in zip(
        prog_out.data.conformers, prog_out.data.conformer_energies, strict=True
    ):
        out_geo = structure.geometry(struct)
        store.geometry(db, geo=out_geo)
        store.calc_geo_link(db, calc=out_calc, geo=out_geo, role=Role.output)

        store.energy(db, calc=out_calc, geo=out_geo, value=energy)
        yield store.stationary_point(db, calc=out_calc, geo=out_geo, order=order)


def scan(
    db: Database,
    *,
    calc: Calculation,
    geo: Geometry,
    idx1: int,
    idx2: int,
    dist1: float,
    dist2: float,
    nsteps: int,
) -> Iterator[StationaryPointRow]:
    """Run a scan between idx1 and idx2 from dist1 to dist2 in nsteps."""
    inp_calc, inp_geo = utils.prepare_inputs(
        db, calc=calc, geo=geo, calc_type=CalcType.conformer_search
    )
