"""Tests for autoengine.run's optimization driver."""

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
import qcdata
from autostorage import Database, GeometryRow, ModelRow
from autostorage.exc import MissingPrimaryKeyError

from autoengine import run
from autoengine.adapter import InputProvenance


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    """In-memory-backed database fixture."""
    database = Database(tmp_path / "test.db")
    yield database
    database.close()


@pytest.fixture
def geometry_row(db: Database) -> GeometryRow:
    """Return a persisted GeometryRow fixture for testing."""
    geo = GeometryRow(
        symbols=["O", "H", "H"],
        coordinates=np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 0.96], [0.93, 0.0, -0.24]]),
        charge=0,
        spin=0,
    )
    return geo.save(db)


@pytest.fixture
def model_row(db: Database) -> ModelRow:
    """Return a persisted ModelRow fixture for testing."""
    model = ModelRow(program="orca", method="wb97x-d3", basis="def2-svp")
    return model.save(db)


def _fake_program_output(geo: GeometryRow) -> MagicMock:
    structure = qcdata.Structure(
        symbols=geo.symbols,
        geometry=np.asarray(geo.coordinates),
        charge=geo.charge,
        multiplicity=geo.spin + 1,
    )
    output = MagicMock()
    output.provenance = qcdata.Provenance(program="orca")
    output.data.final_structure = structure
    return output


def test__optimization_runs_and_caches(
    db: Database,
    geometry_row: GeometryRow,
    model_row: ModelRow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """First call runs the calculation; a repeat call returns the cached row."""
    calls = []

    def fake_compute(program: str, input_data: object, **_kwargs: object) -> MagicMock:
        calls.append((program, input_data))
        return _fake_program_output(geometry_row)

    monkeypatch.setattr(run.qccompute, "compute", fake_compute)

    stationary = run.optimization(db, geometry_row, model_row, InputProvenance())
    assert stationary.id is not None
    assert stationary.calculation.calc_type.value == "optimization"
    assert len(calls) == 1

    stationary2 = run.optimization(db, geometry_row, model_row, InputProvenance())
    assert stationary2.id == stationary.id
    assert len(calls) == 1


def test__optimization_requires_persisted_rows() -> None:
    """Unsaved geometry/model rows (no primary key) are rejected."""
    geo = GeometryRow(symbols=["H"], coordinates=np.zeros((1, 3)), charge=0, spin=0)
    model = ModelRow(program="orca", method="hf", basis="sto-3g")

    with pytest.raises(MissingPrimaryKeyError):
        run.optimization(None, geo, model, InputProvenance())  # ty:ignore[invalid-argument-type]
