"""Core utilities."""

from autostorage import verify_single_iteration

from ..qc import compute
from ..types import (
    CalcType,
    Calculation,
    CalculationRow,
    Database,
    Geometry,
    GeometryRow,
    ProgramOutput,
)
from . import query, store

# Re-exports
__all__ = ["verify_single_iteration"]


def prepare_inputs(
    db: Database, *, calc: Calculation, geo: Geometry, calc_type: CalcType
) -> tuple[CalculationRow, GeometryRow]:
    """Prepare inputs for calculation."""
    inp_calc = CalculationRow.from_calculation(calc, calc_type=calc_type)

    inp_geos = query.geometry(db, geo=geo)
    inp_geo = next(inp_geos, None)

    if next(inp_geos, None):
        msg = f"Multiple matching geometries found in database.\n{geo = }"
        raise LookupError(msg)

    if not inp_geo:
        inp_geo = store.geometry(db, geo=geo)

    return inp_calc, inp_geo


def run_calculation(*, inp_calc: CalculationRow, inp_geo: GeometryRow) -> ProgramOutput:
    """Run calculation with qccompute."""
    prog = inp_calc.super_program or inp_calc.program
    prog_inp = inp_calc.program_input(input_geo=inp_geo)
    return compute(prog, prog_inp)
