"""Interface for running AutoEngine."""

from typing import Any

import qccompute
from automol import Algorithm, Identity, geom
from autostorage import (
    CalculationRow,
    Database,
    GeometryRow,
    IdentityRow,
    ModelRow,
    Role,
    StationaryPointRow,
)
from autostorage.exc import MissingPrimaryKeyError
from autostorage.models import StationaryIdentityLink
from autostorage.types import CalcType
from sqlmodel import select

from .adapter import (
    InputProvenance,
    OutputProvenance,
    calculation_to_program_input,
    structure_to_geometry_row,
)


def _existing_optimization(
    db: Database, geo: GeometryRow, model: ModelRow, input_provenance: dict[str, Any]
) -> StationaryPointRow | None:
    """Find a prior OPT result for the same conformer, if one exists.

    Matches on chemical identity (InChI) and model/provenance rather than
    ``geo``'s row id, then confirms conformer equality (via iRMSD) against
    the input geometry of each candidate calculation. This catches the case
    where ``geo`` is a different row from an already-optimized input that
    represents the same conformer.
    """
    try:
        ident = Identity.from_geometry(geo, algorithm=Algorithm.RDKIT_INCHI)
    except ValueError:
        return None

    stmt = (
        select(StationaryPointRow)
        .join(
            StationaryIdentityLink,
            StationaryPointRow.id == StationaryIdentityLink.stationary_id,  # ty:ignore[invalid-argument-type]
        )
        .join(
            IdentityRow,
            IdentityRow.id == StationaryIdentityLink.identity_id,  # ty:ignore[invalid-argument-type]
        )
        .join(
            CalculationRow,
            StationaryPointRow.calculation_id == CalculationRow.id,  # ty:ignore[invalid-argument-type]
        )
        .where(
            IdentityRow.kind == ident.kind,
            IdentityRow.algorithm == ident.algorithm,
            IdentityRow.value == ident.value,
            CalculationRow.model_id == model.id,
            CalculationRow.calc_type == CalcType.OPT,
            CalculationRow.input_provenance == input_provenance,
        )
    )
    for candidate in db.exec_all(stmt):
        input_geos = [
            link.geometry
            for link in candidate.calculation.geometry_links
            if link.role == Role.INPUT
        ]
        if any(geom.is_duplicate_conformer(geo, input_geos)):
            return candidate

    return None


def _existing_conformer_search(
    db: Database, geo: GeometryRow, model: ModelRow, input_provenance: dict[str, Any]
) -> CalculationRow | None:
    """Find a prior CONFORMER calculation for the same conformer, if one exists.

    Matches on chemical identity (InChI) and model/provenance rather than
    ``geo``'s row id, then confirms conformer equality (via iRMSD) against
    the input geometry of each candidate calculation. Unlike
    ``_existing_optimization``, a conformer search calculation produces many
    output stationary points rather than one, so the match is returned at the
    ``CalculationRow`` level.
    """
    try:
        ident = Identity.from_geometry(geo, algorithm=Algorithm.RDKIT_INCHI)
    except ValueError:
        return None

    stmt = (
        select(CalculationRow)
        .join(
            StationaryPointRow,
            StationaryPointRow.calculation_id == CalculationRow.id,  # ty:ignore[invalid-argument-type]
        )
        .join(
            StationaryIdentityLink,
            StationaryPointRow.id == StationaryIdentityLink.stationary_id,  # ty:ignore[invalid-argument-type]
        )
        .join(
            IdentityRow,
            IdentityRow.id == StationaryIdentityLink.identity_id,  # ty:ignore[invalid-argument-type]
        )
        .where(
            IdentityRow.kind == ident.kind,
            IdentityRow.algorithm == ident.algorithm,
            IdentityRow.value == ident.value,
            CalculationRow.model_id == model.id,
            CalculationRow.calc_type == CalcType.CONFORMER,
            CalculationRow.input_provenance == input_provenance,
        )
        .distinct()
    )
    for candidate in db.exec_all(stmt):
        input_geos = [
            link.geometry
            for link in candidate.geometry_links
            if link.role == Role.INPUT
        ]
        if any(geom.is_duplicate_conformer(geo, input_geos)):
            return candidate

    return None


def conformer_search(
    db: Database, geo: GeometryRow, model: ModelRow, prov: InputProvenance
) -> list[StationaryPointRow]:
    """Run a conformer search calculation.

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
        The resulting stationary point rows, one per conformer found, sorted
        by ascending energy. May be empty if no conformers were found.
    """
    if geo.id is None or model.id is None:
        raise MissingPrimaryKeyError([geo, model])

    input_provenance = prov.model_dump(mode="json")

    # 1. Query the database for a matching conformer search calculation
    existing = _existing_conformer_search(db, geo, model, input_provenance)
    if existing is not None:
        stmt = (
            select(StationaryPointRow)
            .where(StationaryPointRow.calculation_id == existing.id)
            .order_by(StationaryPointRow.id)  # ty:ignore[invalid-argument-type]
        )
        return list(db.exec_all(stmt))

    # 2. Convert the geometry row and model row to a ProgramInput
    calc = CalculationRow(
        model=model, calc_type=CalcType.CONFORMER, input_provenance=input_provenance
    )
    program_input = calculation_to_program_input(calc, geo)

    # 3. Run the calculation
    program_output = qccompute.compute(model.program, program_input)

    # 4. Convert the resulting ProgramOutput to StationaryPointRows
    out_prov = OutputProvenance.model_validate(program_output.provenance.model_dump())
    calc.output_provenance = out_prov.model_dump(mode="json")
    calc = calc.save(db)

    calc.geometry_link(geo, Role.INPUT).save(db)

    stationaries = []
    for structure in program_output.data.conformers:
        out_geo = structure_to_geometry_row(structure).save(db)
        calc.geometry_link(out_geo, Role.OUTPUT).save(db)
        stationaries.append(out_geo.stationary_point(calc).save(db))

    # 5. Return the StationaryPointRows
    return stationaries


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
    existing = _existing_optimization(db, geo, model, input_provenance)
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
