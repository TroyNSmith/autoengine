"""Fixtures for tests."""

from collections.abc import Iterator

import pytest

from autoengine import Calculation, Database, Geometry


@pytest.fixture
def db() -> Iterator[Database]:
    """In-memory blank database fixture."""
    db = Database(":memory:")
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def calc() -> Calculation:
    """Fixture for sample Calculation."""
    return Calculation(program="crest", method="gfnff")


@pytest.fixture
def geo() -> Geometry:
    """Fixture for sample Geometry."""
    return Geometry(
        symbols=["O", "H", "H"],
        coordinates=[[0, 0, 0], [1, 0, 0], [0, 1, 0]],  # ty:ignore[invalid-argument-type]
        charge=0,
        spin=0,
    )
