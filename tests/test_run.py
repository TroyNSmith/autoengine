"""Run module tests."""

from autoengine import Calculation, Database, Geometry, run


def test__energy(db: Database, calc: Calculation, geo: Geometry) -> None:
    """Test successful energy run with crest."""
    ene_rows = run.energy(db, calc=calc, geo=geo)
    raise ValueError(ene_rows)
