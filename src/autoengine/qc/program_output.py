"""Convert ProgramOutput to database rows."""

from ..types import CalculationRow, DualProgramInput, ProgramOutput, ProvenanceRow


def calculation(prog_out: ProgramOutput) -> CalculationRow:
    """
    Instantiate CalculationRow from ProgramOutput.

    **Automatically instantiates and relates ProvenanceRow.

    Parameters
    ----------
    prog_out
        qccompute ProgramOutput.

    Returns
    -------
    CalculationRow
        Validated calculation row with provenance.
    """
    prog_inp = prog_out.input_data
    prov = prog_out.provenance

    if isinstance(prog_inp, DualProgramInput):
        data = {
            "program": prog_inp.subprogram,
            "program_keywords": prog_inp.subprogram_args.keywords,
            "super_program": prov.program,
            "super_keywords": prog_inp.keywords,
            "cmdline_args": prog_inp.subprogram_args.cmdline_args,
            "calc_type": prog_inp.calctype.value,
            "method": prog_inp.subprogram_args.model.method,
            "basis": prog_inp.subprogram_args.model.basis,
        }

    else:
        data = {
            "program": prov.program,
            "program_keywords": prog_inp.keywords,
            "cmdline_args": prog_inp.cmdline_args,
            "calc_type": prog_inp.calctype.value,
            "method": prog_inp.model.method,
            "basis": prog_inp.model.basis,
        }

    calc_row = CalculationRow.model_validate(data)
    calc_row.provenance = provenance(prog_out)
    return calc_row


def provenance(prog_out: ProgramOutput) -> ProvenanceRow:
    """Instantiate ProvenanceRow from ProgramOutput."""
    prog_inp = prog_out.input_data
    prov = prog_out.provenance
    data = prog_out.data

    if isinstance(prog_inp, DualProgramInput):
        traj_prov = [t.provenance for t in data.trajectory]
        data = {
            "program_version": traj_prov[0].program_version,
            "super_version": prov.program_version,
            "input": None,  # Could be used to store .inp (or equivalent) files
            "files": {
                "program": prog_inp.subprogram_args.files,
                "super_program": prog_inp.files,
            },
            "scratch_dir": prov.scratch_dir,
            "wall_time": prov.wall_time,
            "host_name": prov.hostname,
            "host_cpus": prov.hostcpus,
            "host_mem": prov.hostmem,
            "extras": {
                "super_program": prog_inp.extras,
                "program": prog_inp.subprogram_args.extras,
            },
        }

    else:
        data = {
            "program_version": prov.program_version,
            "input": None,  # Could be used to store .inp (or equivalent) files
            "files": {"program": prog_inp.files},
            "scratch_dir": prov.scratch_dir,
            "wall_time": prov.wall_time,
            "host_name": prov.hostname,
            "host_cpus": prov.hostcpus,
            "host_mem": prov.hostmem,
            "extras": {"program": prog_inp.extras},
        }

    return ProvenanceRow.model_validate(data)
