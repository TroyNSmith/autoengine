"""Conversion interface between qcdata and autostorage types."""

from typing import Any

import numpy as np
import qcdata
from automol.utils.constants import ANGSTROM_TO_BOHR
from autostorage import CalculationRow, GeometryRow, ModelRow
from autostorage.types import CalcType
from pydantic import BaseModel


def greet(name: str) -> str:
    """Greet a person by their name.

    Parameters
    ----------
    name :
        The name of the person to greet.

    Returns
    -------
        A greeting message.
    """
    return f"Hello, {name}!"


# CalcType mapping
_CALC_TYPE_TO_QC: dict[CalcType, qcdata.CalcType] = {
    CalcType.OPT: qcdata.CalcType.optimization,
    CalcType.OPT_TS: qcdata.CalcType.transition_state,
    CalcType.CONFORMER: qcdata.CalcType.conformer_search,
    CalcType.SCAN: qcdata.CalcType.scan,
    CalcType.ENERGY: qcdata.CalcType.energy,
    CalcType.GRADIENT: qcdata.CalcType.gradient,
    CalcType.FREQUENCY: qcdata.CalcType.hessian,
}
_QC_CALC_TYPE_TO_ROW: dict[qcdata.CalcType, CalcType] = {
    v: k for k, v in _CALC_TYPE_TO_QC.items()
}


def calc_type_to_qc(calc_type: CalcType) -> qcdata.CalcType:
    """Convert an autostorage CalcType to a qcdata CalcType.

    Parameters
    ----------
    calc_type :
        The autostorage calculation type.

    Returns
    -------
        The corresponding qcdata calculation type.

    Examples
    --------
    >>> calc_type_to_qc(CalcType.OPT)
    'optimization'
    """
    if calc_type not in _CALC_TYPE_TO_QC:
        msg = (
            f"{calc_type!r} has no qcdata CalcType equivalent — it is a "
            "post-processing/analysis step, not a program-driven run type."
        )
        raise ValueError(msg)
    return _CALC_TYPE_TO_QC[calc_type]


def qc_calc_type_to_row(calc_type: qcdata.CalcType) -> CalcType:
    """Convert a qcdata CalcType to an autostorage CalcType.

    Parameters
    ----------
    calc_type :
        The qcdata calculation type.

    Returns
    -------
        The corresponding autostorage calculation type.

    Examples
    --------
    >>> qc_calc_type_to_row(qcdata.CalcType.optimization)
    <CalcType.OPT: 'optimization'>
    """
    return _QC_CALC_TYPE_TO_ROW[calc_type]


# Provenance models
class SubprogramModel(BaseModel):
    """Method/basis for a DualProgramInput's inner subprogram."""

    method: str
    basis: str | None = None


class InputProvenance(BaseModel):
    """Data needed to reconstruct a ProgramInput/DualProgramInput.

    Round-trips through CalculationRow.input_provenance, filling gaps that
    ModelRow/CalculationRow don't otherwise carry.
    """

    keywords: dict[str, Any] = {}
    cmdline_args: list[str] = []
    files: dict[str, str | bytes] = {}
    extras: dict[str, Any] = {}
    # DualProgramInput's outer/driver layer only
    driver_program: str | None = None
    driver_model: SubprogramModel | None = None
    driver_keywords: dict[str, Any] = {}
    driver_cmdline_args: list[str] = []


class OutputProvenance(BaseModel):
    """Provenance metadata produced by a calculation.

    Mirrors qcdata.Provenance, and round-trips through
    CalculationRow.output_provenance.
    """

    program: str | None = None
    program_version: str | None = None
    scratch_dir: str | None = None
    wall_time: float | None = None
    hostname: str | None = None
    hostcpus: int | None = None
    hostmem: int | None = None


# Geometry <-> Structure
def geometry_row_to_structure(geo: GeometryRow) -> qcdata.Structure:
    """Convert a GeometryRow to a qcdata Structure.

    Parameters
    ----------
    geo :
        The geometry row.

    Returns
    -------
        The corresponding qcdata structure.
    """
    return qcdata.Structure(
        symbols=geo.symbols,
        geometry=np.asarray(geo.coordinates) * ANGSTROM_TO_BOHR,
        charge=geo.charge,
        multiplicity=geo.spin + 1,
    )


def structure_to_geometry_row(struct: qcdata.Structure) -> GeometryRow:
    """Convert a qcdata Structure to an unsaved GeometryRow.

    Parameters
    ----------
    struct :
        The qcdata structure.

    Returns
    -------
        The corresponding, unsaved geometry row.
    """
    return GeometryRow(
        symbols=list(struct.symbols),
        coordinates=struct.geometry_angstrom,
        charge=struct.charge,
        spin=struct.multiplicity - 1,
    )


# Model <-> Model
def model_row_to_qc_model(model: ModelRow) -> qcdata.Model:
    """Convert a ModelRow to a qcdata Model.

    Parameters
    ----------
    model :
        The model row.

    Returns
    -------
        The corresponding qcdata model.
    """
    return qcdata.Model(method=model.method, basis=model.basis)


def qc_model_to_model_row(
    qc_model: qcdata.Model, *, program: str, program_version: str | None = None
) -> ModelRow:
    """Convert a qcdata Model to an unsaved ModelRow.

    Parameters
    ----------
    qc_model :
        The qcdata model.
    program :
        The program that executes this model (not carried by qcdata.Model).
    program_version :
        The program version, if known.

    Returns
    -------
        The corresponding, unsaved model row.
    """
    return ModelRow(
        program=program,
        program_version=program_version,
        method=qc_model.method,
        basis=qc_model.basis,
    )


# Calculation <-> ProgramInput
def calculation_to_program_input(
    calc: CalculationRow, geo: GeometryRow
) -> qcdata.ProgramInput:
    """Convert a CalculationRow/GeometryRow pair to a qcdata ProgramInput.

    Parameters
    ----------
    calc :
        The calculation row.
    geo :
        The input geometry row.

    Returns
    -------
        The corresponding qcdata program input.
    """
    prov = InputProvenance.model_validate(calc.input_provenance or {})
    return qcdata.ProgramInput(
        calctype=calc_type_to_qc(calc.calc_type),
        model=model_row_to_qc_model(calc.model),
        structure=geometry_row_to_structure(geo),
        keywords=prov.keywords,
        cmdline_args=prov.cmdline_args,
        files=prov.files,
        extras=prov.extras,
    )


def program_input_to_calculation(
    pi: qcdata.ProgramInput, *, program: str, program_version: str | None = None
) -> tuple[CalculationRow, GeometryRow]:
    """Convert a qcdata ProgramInput to an unsaved, unlinked row pair.

    Parameters
    ----------
    pi :
        The qcdata program input.
    program :
        The program that executes this input (not carried by ProgramInput).
    program_version :
        The program version, if known.

    Returns
    -------
        The corresponding, unsaved calculation and geometry rows.
    """
    geo = structure_to_geometry_row(pi.structure)
    model = qc_model_to_model_row(
        pi.model, program=program, program_version=program_version
    )
    prov = InputProvenance(
        keywords=pi.keywords,
        cmdline_args=pi.cmdline_args,
        files=pi.files,
        extras=pi.extras,
    )
    calc = CalculationRow(
        model=model,
        calc_type=qc_calc_type_to_row(pi.calctype),
        input_provenance=prov.model_dump(mode="json"),
    )
    return calc, geo


# Calculation <-> DualProgramInput
def calculation_to_dual_program_input(
    calc: CalculationRow, geo: GeometryRow
) -> qcdata.DualProgramInput:
    """Convert a CalculationRow/GeometryRow pair to a qcdata DualProgramInput.

    CalculationRow.model represents the subprogram that actually executes the
    level of theory (whose name is calc.model.program); the driver layer is
    read from CalculationRow.input_provenance's driver_* fields.

    Parameters
    ----------
    calc :
        The calculation row.
    geo :
        The input geometry row.

    Returns
    -------
        The corresponding qcdata dual program input.
    """
    prov = InputProvenance.model_validate(calc.input_provenance or {})
    driver_model = (
        qcdata.Model(method=prov.driver_model.method, basis=prov.driver_model.basis)
        if prov.driver_model
        else None
    )
    return qcdata.DualProgramInput(
        calctype=calc_type_to_qc(calc.calc_type),
        model=driver_model,
        structure=geometry_row_to_structure(geo),
        keywords=prov.driver_keywords,
        cmdline_args=prov.driver_cmdline_args,
        subprogram=calc.model.program,
        subprogram_args=qcdata.ProgramArgs(
            model=model_row_to_qc_model(calc.model),
            keywords=prov.keywords,
            cmdline_args=prov.cmdline_args,
        ),
    )


def dual_program_input_to_calculation(
    pi: qcdata.DualProgramInput, *, program_version: str | None = None
) -> tuple[CalculationRow, GeometryRow]:
    """Convert a qcdata DualProgramInput to an unsaved, unlinked row pair.

    CalculationRow.model is built from the subprogram (the program that
    actually executes the level of theory); the driver layer is stored in
    CalculationRow.input_provenance's driver_* fields.

    Parameters
    ----------
    pi :
        The qcdata dual program input.
    program_version :
        The subprogram's version, if known (not carried by DualProgramInput).

    Returns
    -------
        The corresponding, unsaved calculation and geometry rows.
    """
    geo = structure_to_geometry_row(pi.structure)
    model = qc_model_to_model_row(
        pi.subprogram_args.model,
        program=pi.subprogram,
        program_version=program_version,
    )
    driver_model = (
        SubprogramModel(method=pi.model.method, basis=pi.model.basis)
        if pi.model
        else None
    )
    prov = InputProvenance(
        keywords=pi.subprogram_args.keywords,
        cmdline_args=pi.subprogram_args.cmdline_args,
        files=pi.files,
        extras=pi.extras,
        driver_model=driver_model,
        driver_keywords=pi.keywords,
        driver_cmdline_args=pi.cmdline_args,
    )
    calc = CalculationRow(
        model=model,
        calc_type=qc_calc_type_to_row(pi.calctype),
        input_provenance=prov.model_dump(mode="json"),
    )
    return calc, geo
