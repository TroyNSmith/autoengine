"""Interface for running AutoEngine."""

import qccompute
from autostorage import (
    CalculationGeometryLink,
    CalculationRow,
    Database,
    GeometryRow,
    ModelRow,
    Role,
    StationaryPointRow,
)
from autostorage.exc import MissingPrimaryKeyError
from autostorage.types import CalcType
from sqlmodel import select

from .adapter import (
    InputProvenance,
    OutputProvenance,
    calculation_to_program_input,
    structure_to_geometry_row,
)


def optimization(
    db: Database, geo: GeometryRow, model: ModelRow, prov: InputProvenance
) -> StationaryPointRow:
    """Run an optimization calculation.

    Parameters
    ----------
    db :
        The database connection.
    geo :
        The input geometry row.
    model :
        The model row.
    prov :
        The input provenance.

    Returns
    -------
        The resulting stationary point row.
    """
    if geo.id is None or model.id is None:
        raise MissingPrimaryKeyError([geo, model])

    input_provenance = prov.model_dump(mode="json")

    # 1. Query the database for a matching stationary point row
    stmt = (
        select(StationaryPointRow)
        .join(CalculationRow)
        .join(CalculationGeometryLink)
        .where(
            CalculationGeometryLink.geometry_id == geo.id,
            CalculationGeometryLink.role == Role.INPUT,
            CalculationRow.model_id == model.id,
            CalculationRow.calc_type == CalcType.OPT,
            CalculationRow.input_provenance == input_provenance,
        )
    )
    existing = db.exec_first(stmt)
    if existing is not None:
        return existing

    # 2. Convert the geometry row and model row to a ProgramInput
    calc = CalculationRow(
        model=model, calc_type=CalcType.OPT, input_provenance=input_provenance
    )
    program_input = calculation_to_program_input(calc, geo)

    # 3. Run the calculation
    program_output = qccompute.compute(model.program, program_input)

    # 4. Convert the resulting ProgramOutput to a StationaryPointRow
    out_prov = OutputProvenance.model_validate(program_output.provenance.model_dump())
    calc.output_provenance = out_prov.model_dump(mode="json")
    calc = calc.save(db)

    out_geo = structure_to_geometry_row(program_output.data.final_structure).save(db)
    calc.geometry_link(geo, Role.INPUT).save(db)
    calc.geometry_link(out_geo, Role.OUTPUT).save(db)

    stationary = out_geo.stationary_point(calc)

    # 5. Save the StationaryPointRow to the database
    # 6. Return the StationaryPointRow
    return stationary.save(db)
