"""Convert Structure to database rows."""

import pint

from ..types import GeometryRow, Structure


def geometry(struc: Structure) -> GeometryRow:
    """
    Instantiate GeometryRow from Structure.

    Parameters
    ----------
    struc
        The qcdata Structure to convert.

    Returns
    -------
    GeometryRow
        GeometryRow in Angstrom.
    """
    return GeometryRow(
        symbols=struc.symbols,
        coordinates=struc.geometry * pint.Quantity("bohr").m_as("angstrom"),
        charge=struc.charge,
        spin=struc.multiplicity - 1,
    )
