"""Tests for autoengine.adapter's qcdata/autostorage conversion interface."""

import numpy as np
import pytest
import qcdata
from autostorage import CalculationRow, GeometryRow, ModelRow
from autostorage.types import CalcType

from autoengine import adapter


@pytest.fixture
def geometry_row() -> GeometryRow:
    """GeometryRow fixture for testing."""
    return GeometryRow(
        symbols=["O", "H", "H"],
        coordinates=np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 0.96], [0.93, 0.0, -0.24]]),
        charge=0,
        spin=0,
    )


@pytest.fixture
def model_row() -> ModelRow:
    """ModelRow fixture for testing."""
    return ModelRow(program="orca", method="wb97x-d3", basis="def2-svp")


def test__geometry_row_structure_round_trip(geometry_row: GeometryRow) -> None:
    """Geometry row -> Structure -> geometry row round-trips coordinates/spin."""
    geo = geometry_row
    struct = adapter.geometry_row_to_structure(geo)

    assert struct.symbols == geo.symbols
    assert struct.charge == geo.charge
    assert struct.multiplicity == geo.spin + 1
    assert np.allclose(struct.geometry_angstrom, geo.coordinates)

    geo2 = adapter.structure_to_geometry_row(struct)
    assert geo2.symbols == geo.symbols
    assert geo2.charge == geo.charge
    assert geo2.spin == geo.spin
    assert np.allclose(geo2.coordinates, geo.coordinates)


def test__model_row_qc_model_round_trip(model_row: ModelRow) -> None:
    """Model row -> Model -> model row round-trips method/basis/program."""
    model = model_row
    qc_model = adapter.model_row_to_qc_model(model)

    assert qc_model.method == model.method
    assert qc_model.basis == model.basis

    model2 = adapter.qc_model_to_model_row(qc_model, program=model.program)
    assert model2.program == model.program
    assert model2.method == model.method
    assert model2.basis == model.basis


def test__calculation_program_input_round_trip(
    geometry_row: GeometryRow, model_row: ModelRow
) -> None:
    """Calculation row -> ProgramInput -> calculation row round-trips fields."""
    geo = geometry_row
    model = model_row
    calc = CalculationRow(
        model=model,
        calc_type=CalcType.ENERGY,
        input_provenance={"keywords": {"maxiter": 250}},
    )

    pi = adapter.calculation_to_program_input(calc, geo)
    assert pi.calctype == qcdata.CalcType.energy
    assert pi.model.method == model.method
    assert pi.keywords == {"maxiter": 250}

    calc2, geo2 = adapter.program_input_to_calculation(pi, program=model.program)
    assert calc2.calc_type == CalcType.ENERGY
    assert calc2.model.program == model.program
    assert calc2.model.method == model.method
    assert np.allclose(geo2.coordinates, geo.coordinates)


def test__calculation_dual_program_input_round_trip(
    geometry_row: GeometryRow, model_row: ModelRow
) -> None:
    """Calculation row -> DualProgramInput -> calculation row round-trips fields."""
    geo = geometry_row
    model = model_row
    calc = CalculationRow(
        model=model,
        calc_type=CalcType.OPT,
        input_provenance={
            "keywords": {"scf_type": "df"},
            "driver_program": "geometric",
            "driver_keywords": {"maxiter": 100},
        },
    )

    pi = adapter.calculation_to_dual_program_input(calc, geo)
    assert pi.subprogram == model.program
    assert pi.subprogram_args.model.method == model.method
    assert pi.keywords == {"maxiter": 100}

    calc2, geo2 = adapter.dual_program_input_to_calculation(pi)
    assert calc2.calc_type == CalcType.OPT
    assert calc2.model.program == model.program
    assert calc2.model.method == model.method
    assert np.allclose(geo2.coordinates, geo.coordinates)


@pytest.mark.parametrize(
    "calc_type", [CalcType.IRC, CalcType.MEP, CalcType.THERMO, CalcType.UNDEFINED]
)
def test__calc_type_to_qc_raises_for_unsupported(calc_type: CalcType) -> None:
    """Analysis-only calc types have no qcdata CalcType equivalent."""
    with pytest.raises(ValueError, match="no qcdata CalcType equivalent"):
        adapter.calc_type_to_qc(calc_type)
