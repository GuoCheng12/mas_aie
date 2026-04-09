from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from aie_mas.agents.result_agents import MicroscopicAgent
from aie_mas.chem.structure_prep import PreparedStructure, StructurePrepError
from aie_mas.cli.run_case import run_case_workflow
from aie_mas.graph import builder as graph_builder
from aie_mas.graph.state import MicroscopicTaskSpec
from aie_mas.graph.state import MicroscopicExecutionPlan
from aie_mas.graph.state import DihedralDescriptor
from aie_mas.graph.state import MicroscopicToolCall
from aie_mas.graph.state import MicroscopicToolPlan
from aie_mas.graph.state import MicroscopicToolRequest
from aie_mas.graph.state import SelectionPolicy
from aie_mas.tools.amesp import (
    AmespBaselineMicroscopicTool,
    AmespExecutionError,
    AmespExcitedState,
    AmespExcitedStateResult,
    AmespGroundStateResult,
    AmespBaselineRunResult,
    _approximate_delta_dipole,
    _approximate_dipole_from_charges_and_coordinates,
    _read_xyz_symbols_and_coordinates,
)
from aie_mas.tools.factory import ToolSet
from aie_mas.tools.macro import DeterministicMacroStructureTool
from aie_mas.tools.shared_structure import SharedStructurePrepTool


S0_AOP_TEXT = """
HOMO-LUMO gap:      0.5141800 AU    =     322.6530833 Kcal/mol
             =      13.9915470 eV    =    1349.9795543  KJ/mol

Mulliken charges:

     1   N        -0.431647
     2   H         0.143878
     3   H         0.143884
     4   H         0.143884
Sum of Mulliken charges =     -0.00000

Dipole moment (field-independent basis, Debye):

  X=     1.9615    Y=    -0.0007    Z=    -0.0000    Tot=     1.9615

Final Geometry(angstroms):

  4
  N            1.20237169    0.76811388    0.00000037
  H            1.68575703   -0.17839889   -0.00000014
  H            1.68624551    1.24109381    0.81953316
  H            1.68624381    1.24109377   -0.81953339

Final Energy:      -55.7914717877
Normal termination of Amesp!
"""

S1_AOP_TEXT = """
========= Excitation energies and oscillator strengths =========
State    1 : E =    3.8474 eV     322.276 nm      31032.13 cm-1
       4 -->  5      0.8123400
E(TD) =   -55.650000000      <S**2>= 0.000     f=  0.1234
State    2 : E =    4.6637 eV     265.850 nm      37615.42 cm-1
       3 -->  5     -0.4012300
       4 -->  6      0.5223400
E(TD) =   -55.620000000      <S**2>= 0.000     f=  0.0100

Final Geometry(angstroms):

  4
  N            1.20237169    0.76811388    0.00000037
  H            1.68575703   -0.17839889   -0.00000014
  H            1.68624551    1.24109381    0.81953316
  H            1.68624381    1.24109377   -0.81953339

Final Energy:      -55.7914717877
Normal termination of Amesp!
"""

S1_TRANSITION_DIPOLE_AOP_TEXT = """
Ground to excited state transition electric dipole moments(Au):
  state-state      X         Y        Z         Dip       Osc
    0     1     0.1200    0.0000    0.0100    0.1204    0.1234
    0     2     0.0500    0.0100    0.0000    0.0510    0.0100

Excited to excited state transition electric dipole moments(Au):
  state-state        X            Y            Z          Osc
    1     1      -0.0000      -0.0000      -0.0075      0.0000
    1     2      -0.0000       0.0000       0.7309      0.0082

""" + S1_AOP_TEXT

S1_OPT_AOP_TEXT = """
Mulliken charges:

     1   N        -0.401647
     2   H         0.133878
     3   H         0.133884
     4   H         0.133885
Sum of Mulliken charges =     -0.00000

Dipole moment (field-independent basis, Debye):

  X=     1.1050    Y=     0.2120    Z=     0.0510    Tot=     1.1264

========= Excitation energies and oscillator strengths =========
State    1 : E =    2.7310 eV     453.992 nm      22026.81 cm-1
       4 -->  5      0.8123400
E(TD) =   -55.650000000      <S**2>= 0.000     f=  0.6005
State    2 : E =    3.1793 eV     389.969 nm      25643.02 cm-1
       3 -->  5     -0.4012300
       4 -->  6      0.5223400
E(TD) =   -55.620000000      <S**2>= 0.000     f=  0.0100

Final Geometry(angstroms):

  4
  N            1.23000000    0.79200000    0.01000000
  H            1.70200000   -0.13200000    0.02200000
  H            1.70400000    1.26600000    0.83800000
  H            1.70500000    1.26700000   -0.80400000

Final Energy:      -55.6500000000
Normal termination of Amesp!
"""

S1_OPT_MISMATCH_AOP_TEXT = """
Mulliken charges:

     1   H        -0.401647
     2   N         0.133878
     3   H         0.133884
     4   H         0.133885
Sum of Mulliken charges =     -0.00000

Dipole moment (field-independent basis, Debye):

  X=     1.1050    Y=     0.2120    Z=     0.0510    Tot=     1.1264

========= Excitation energies and oscillator strengths =========
State    1 : E =    2.7310 eV     453.992 nm      22026.81 cm-1
       4 -->  5      0.8123400
E(TD) =   -55.650000000      <S**2>= 0.000     f=  0.6005

Final Geometry(angstroms):

  4
  N            1.23000000    0.79200000    0.01000000
  H            1.70200000   -0.13200000    0.02200000
  H            1.70400000    1.26600000    0.83800000
  H            1.70500000    1.26700000   -0.80400000

Final Energy:      -55.6500000000
Normal termination of Amesp!
"""

S0_AOP_GEOMETRY_TEXT = """
HOMO-LUMO gap:      0.4010000 AU    =      10.9116660 eV

Mulliken charges:

     1   O        -0.481000
     2   H         0.312000
     3   C         0.141000
     4   N        -0.221000
     5   C         0.249000
Sum of Mulliken charges =      0.00000

Dipole moment (field-independent basis, Debye):

  X=     2.1400    Y=     0.1800    Z=     0.0000    Tot=     2.1476

Final Geometry(angstroms):

  5
  O            0.00000000    0.00000000    0.00000000
  H            0.98000000    0.00000000    0.00000000
  C           -1.32000000    0.00000000    0.00000000
  N            2.55000000    0.20000000    0.00000000
  C            3.72000000    0.20000000    0.00000000

Final Energy:      -210.1234567890
Normal termination of Amesp!
"""


class _FakePositions:
    def __init__(self, rows):
        self._rows = rows

    def tolist(self):
        return self._rows


class _FakeAtoms:
    def __init__(self, symbols, positions):
        self._symbols = symbols
        self._positions = positions

    def get_chemical_symbols(self):
        return list(self._symbols)

    def get_positions(self):
        return _FakePositions(self._positions)


def _fake_structure_preparer(request):
    request.workdir.mkdir(parents=True, exist_ok=True)
    atoms = _FakeAtoms(
        symbols=["N", "H", "H", "H"],
        positions=[
            [1.20, 0.76, 0.00],
            [1.69, -0.17, 0.00],
            [1.68, 1.24, 0.82],
            [1.68, 1.24, -0.82],
        ],
    )
    xyz_path = request.workdir / "prepared_structure.xyz"
    sdf_path = request.workdir / "prepared_structure.sdf"
    summary_path = request.workdir / "structure_prep_summary.json"
    xyz_path.write_text(
        "4\nfake_structure\nN 1.2 0.76 0.0\nH 1.69 -0.17 0.0\nH 1.68 1.24 0.82\nH 1.68 1.24 -0.82\n",
        encoding="utf-8",
    )
    sdf_path.write_text("fake sdf\n", encoding="utf-8")
    prepared = PreparedStructure(
        input_smiles=request.smiles,
        canonical_smiles=request.smiles,
        charge=0,
        multiplicity=1,
        heavy_atom_count=1,
        atom_count=4,
        conformer_count=1,
        selected_conformer_id=0,
        force_field="MMFF94",
        xyz_path=xyz_path,
        sdf_path=sdf_path,
        summary_path=summary_path,
    )
    summary_path.write_text(
        json.dumps(prepared.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return atoms, prepared


def _fake_torsion_snapshot_bundle(*, smiles, prepared, max_total, target_angles, target_dihedral_atoms, output_dir):
    del smiles
    output_dir.mkdir(parents=True, exist_ok=True)
    angles = list(target_angles or [-120.0, 0.0, 120.0])
    dihedral_atoms = list(target_dihedral_atoms or [0, 1, 2, 3])
    snapshots = []
    for index, angle in enumerate(angles[:max_total], start=1):
        snapshot_label = f"torsion_{index:02d}"
        snapshot_dir = output_dir / snapshot_label
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        xyz_path = snapshot_dir / "prepared_structure.xyz"
        sdf_path = snapshot_dir / "prepared_structure.sdf"
        summary_path = snapshot_dir / "structure_prep_summary.json"
        xyz_path.write_text(
            "4\nfake_torsion_snapshot\nC 0.0 0.0 0.0\nC 1.5 0.0 0.0\nC 2.9 0.5 0.0\nC 4.3 0.5 0.0\n",
            encoding="utf-8",
        )
        sdf_path.write_text("fake torsion sdf\n", encoding="utf-8")
        snapshot_prepared = prepared.model_copy(
            update={
                "xyz_path": xyz_path,
                "sdf_path": sdf_path,
                "summary_path": summary_path,
            }
        )
        summary_path.write_text(
            json.dumps(snapshot_prepared.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        snapshots.append(
            {
                "snapshot_label": snapshot_label,
                "dihedral_atoms": dihedral_atoms,
                "target_angle_deg": float(angle),
                "prepared": snapshot_prepared,
                "atoms": _FakeAtoms(
                    symbols=["C", "C", "C", "C"],
                    positions=[
                        [0.0, 0.0, 0.0],
                        [1.5, 0.0, 0.0],
                        [2.9, 0.5, 0.0],
                        [4.3, 0.5, 0.0],
                    ],
                ),
            }
        )
    return snapshots


def _fake_geometry_structure_preparer(request):
    request.workdir.mkdir(parents=True, exist_ok=True)
    atoms = _FakeAtoms(
        symbols=["O", "H", "C", "N", "C"],
        positions=[
            [0.0, 0.0, 0.0],
            [0.98, 0.0, 0.0],
            [-1.32, 0.0, 0.0],
            [2.55, 0.2, 0.0],
            [3.72, 0.2, 0.0],
        ],
    )
    xyz_path = request.workdir / "prepared_structure.xyz"
    sdf_path = request.workdir / "prepared_structure.sdf"
    summary_path = request.workdir / "structure_prep_summary.json"
    xyz_path.write_text(
        "5\nfake_geometry_structure\n"
        "O 0.0 0.0 0.0\n"
        "H 0.98 0.0 0.0\n"
        "C -1.32 0.0 0.0\n"
        "N 2.55 0.2 0.0\n"
        "C 3.72 0.2 0.0\n",
        encoding="utf-8",
    )
    sdf_path.write_text("fake geometry sdf\n", encoding="utf-8")
    prepared = PreparedStructure(
        input_smiles=request.smiles,
        canonical_smiles=request.smiles,
        charge=0,
        multiplicity=1,
        heavy_atom_count=4,
        atom_count=5,
        conformer_count=1,
        selected_conformer_id=0,
        force_field="MMFF94",
        xyz_path=xyz_path,
        sdf_path=sdf_path,
        summary_path=summary_path,
    )
    summary_path.write_text(
        json.dumps(prepared.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return atoms, prepared


def _fake_subprocess_success(cmd, cwd, env, capture_output, text):
    del env, capture_output, text
    workdir = Path(cwd)
    aip_name = Path(cmd[1]).name
    aop_name = Path(cmd[2]).name
    label = Path(aip_name).stem
    if label.endswith("_s0") or label.endswith("_s0sp"):
        aop_text = S0_AOP_TEXT
    else:
        aop_text = S1_AOP_TEXT
    (workdir / aop_name).write_text(aop_text, encoding="utf-8")
    (workdir / f"{label}.mo").write_text("fake mo\n", encoding="utf-8")
    return subprocess.CompletedProcess(cmd, 0, stdout="ok\n", stderr="")


def _fake_geometry_subprocess_success(cmd, cwd, env, capture_output, text):
    del env, capture_output, text
    workdir = Path(cwd)
    aip_name = Path(cmd[1]).name
    aop_name = Path(cmd[2]).name
    label = Path(aip_name).stem
    if label.endswith("_s0") or label.endswith("_s0sp"):
        aop_text = S0_AOP_GEOMETRY_TEXT
    else:
        aop_text = S1_AOP_TEXT
    (workdir / aop_name).write_text(aop_text, encoding="utf-8")
    (workdir / f"{label}.mo").write_text("fake mo\n", encoding="utf-8")
    return subprocess.CompletedProcess(cmd, 0, stdout="ok\n", stderr="")


def _build_fake_subprocess_with_aip_capture(captured_inputs: dict[str, str]):
    def _runner(cmd, cwd, env, capture_output, text):
        del env, capture_output, text
        workdir = Path(cwd)
        aip_name = Path(cmd[1]).name
        aop_name = Path(cmd[2]).name
        label = Path(aip_name).stem
        captured_inputs[label] = (workdir / aip_name).read_text(encoding="utf-8")
        if label.endswith("_s0") or label.endswith("_s0sp"):
            aop_text = S0_AOP_TEXT
        else:
            aop_text = S1_AOP_TEXT
        (workdir / aop_name).write_text(aop_text, encoding="utf-8")
        (workdir / f"{label}.mo").write_text("fake mo\n", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="ok\n", stderr="")

    return _runner


def _build_fake_subprocess_with_env_capture(
    captured_inputs: dict[str, str],
    captured_envs: dict[str, dict[str, str]],
):
    def _runner(cmd, cwd, env, capture_output, text):
        del capture_output, text
        workdir = Path(cwd)
        aip_name = Path(cmd[1]).name
        aop_name = Path(cmd[2]).name
        label = Path(aip_name).stem
        captured_inputs[label] = (workdir / aip_name).read_text(encoding="utf-8")
        captured_envs[label] = dict(env)
        if label.endswith("_s0") or label.endswith("_s0sp"):
            aop_text = S0_AOP_TEXT
        else:
            aop_text = S1_AOP_TEXT
        (workdir / aop_name).write_text(aop_text, encoding="utf-8")
        (workdir / f"{label}.mo").write_text("fake mo\n", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="ok\n", stderr="")

    return _runner


def _build_fake_subprocess_with_targeted_analysis_capture(captured_inputs: dict[str, str]):
    hirshfeld_section = (
        "Hirshfeld charges:\n\n"
        "     1   N        -0.390000\n"
        "     2   H         0.130000\n"
        "     3   H         0.130000\n"
        "     4   H         0.130000\n"
        "Sum of Hirshfeld charges =      0.00000\n\n"
    )
    density_population_section = (
        "Density matrix:\n\n"
        "  1  1   1.9800\n"
        "  1  2   0.1200\n\n"
        "Gross orbital populations:\n\n"
        "  1   N    1.7500\n"
        "  2   H    0.2500\n\n"
        "Mayer bond order:\n\n"
        "  1  2  0.9100\n"
        "  1  3  0.9050\n"
        "  1  4  0.9040\n\n"
    )

    def _runner(cmd, cwd, env, capture_output, text):
        del env, capture_output, text
        workdir = Path(cwd)
        aip_name = Path(cmd[1]).name
        aop_name = Path(cmd[2]).name
        label = Path(aip_name).stem
        aip_text = (workdir / aip_name).read_text(encoding="utf-8")
        captured_inputs[label] = aip_text
        lowered = aip_text.lower()
        if label.endswith("_s0") or label.endswith("_s0sp"):
            aop_text = S0_AOP_TEXT
            if "charge hirshfeld" in lowered:
                aop_text = aop_text.replace(
                    "Dipole moment (field-independent basis, Debye):\n",
                    hirshfeld_section + "Dipole moment (field-independent basis, Debye):\n",
                )
            if "out 2" in lowered:
                aop_text = aop_text.replace(
                    "Final Geometry(angstroms):\n",
                    density_population_section + "Final Geometry(angstroms):\n",
                )
        else:
            aop_text = S1_TRANSITION_DIPOLE_AOP_TEXT if "excdip on" in lowered else S1_AOP_TEXT
        (workdir / aop_name).write_text(aop_text, encoding="utf-8")
        (workdir / f"{label}.mo").write_text("fake mo\n", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="ok\n", stderr="")

    return _runner


def _build_fake_subprocess_with_approx_dipole_capture(
    captured_inputs: dict[str, str],
    *,
    mismatch: bool = False,
):
    def _runner(cmd, cwd, env, capture_output, text):
        del env, capture_output, text
        workdir = Path(cwd)
        aip_name = Path(cmd[1]).name
        aop_name = Path(cmd[2]).name
        label = Path(aip_name).stem
        aip_text = (workdir / aip_name).read_text(encoding="utf-8")
        captured_inputs[label] = aip_text
        lowered = aip_text.lower()
        if label.endswith("_s0") or label.endswith("_s0sp"):
            aop_text = S0_AOP_TEXT
        elif "atb1 tda opt force" in lowered:
            aop_text = S1_OPT_MISMATCH_AOP_TEXT if mismatch else S1_OPT_AOP_TEXT
        else:
            aop_text = S1_AOP_TEXT
        (workdir / aop_name).write_text(aop_text, encoding="utf-8")
        (workdir / f"{label}.mo").write_text("fake mo\n", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="ok\n", stderr="")

    return _runner


def _build_targeted_follow_up_tool(
    *,
    tmp_path: Path,
    monkeypatch,
    subprocess_runner,
) -> AmespBaselineMicroscopicTool:
    amesp_bin = tmp_path / "amesp"
    amesp_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr("aie_mas.tools.amesp._generate_torsion_snapshot_bundle", _fake_torsion_snapshot_bundle)
    return AmespBaselineMicroscopicTool(
        amesp_bin=amesp_bin,
        structure_preparer=_fake_structure_preparer,
        subprocess_runner=subprocess_runner,
        follow_up_max_torsion_snapshots_total=6,
    )


def _run_torsion_source_bundle(
    *,
    tool: AmespBaselineMicroscopicTool,
    tmp_path: Path,
) -> AmespBaselineRunResult:
    return tool.execute(
        plan=MicroscopicExecutionPlan(
            local_goal="Generate torsion snapshots for later targeted property reuse.",
            requested_deliverables=["torsion sensitivity summary"],
            capability_route="torsion_snapshot_follow_up",
            microscopic_tool_request=MicroscopicToolRequest(
                capability_name="run_torsion_snapshots",
                perform_new_calculation=True,
                optimize_ground_state=False,
                artifact_scope="torsion_snapshots",
                dihedral_id="dih_0_1_2_3",
                dihedral_atom_indices=[0, 1, 2, 3],
                snapshot_count=2,
                angle_offsets_deg=[25.0, -25.0],
                state_window=[1, 2, 3],
                deliverables=["torsion sensitivity summary"],
                requested_route_summary="Generate two torsion snapshots for targeted property reuse.",
            ),
            structure_source="prepared_from_smiles",
            failure_reporting="Return partial or failed if Amesp fails.",
        ),
        smiles="N",
        label="targeted_property_source",
        workdir=tmp_path / "targeted_property_source_workdir",
        available_artifacts={},
        round_index=2,
    )


def _run_targeted_property_follow_up(
    *,
    tool: AmespBaselineMicroscopicTool,
    tmp_path: Path,
    torsion_result: AmespBaselineRunResult,
    capability_name: str,
    deliverables: list[str],
    descriptor_scope: list[str] | None = None,
) -> AmespBaselineRunResult:
    return tool.execute(
        plan=MicroscopicExecutionPlan(
            local_goal=f"Reuse the torsion bundle and run {capability_name} on representative geometries.",
            requested_deliverables=deliverables,
            capability_route="targeted_property_follow_up",
            microscopic_tool_request=MicroscopicToolRequest(
                capability_name=capability_name,
                perform_new_calculation=True,
                optimize_ground_state=False,
                artifact_bundle_id="round_02_torsion_snapshots",
                artifact_source_round=2,
                artifact_scope="torsion_snapshots",
                state_window=[1, 2, 3],
                descriptor_scope=descriptor_scope or [],
                target_count=2,
                deliverables=deliverables,
                requested_route_summary=f"Reuse the torsion bundle and rerun {capability_name} on two representative geometries.",
            ),
            structure_source="existing_prepared_structure",
            failure_reporting="Return partial or failed if Amesp fails.",
        ),
        smiles="N",
        label=f"{capability_name}_follow_up",
        workdir=tmp_path / f"{capability_name}_follow_up_workdir",
        available_artifacts={**torsion_result.generated_artifacts, "source_round": 2},
        round_index=4,
    )


def _fake_subprocess_partial_torsion_s1(cmd, cwd, env, capture_output, text):
    del env, capture_output, text
    workdir = Path(cwd)
    aip_name = Path(cmd[1]).name
    aop_name = Path(cmd[2]).name
    label = Path(aip_name).stem
    if label.endswith("_s0") or label.endswith("_s0sp"):
        aop_text = S0_AOP_TEXT
    else:
        aop_text = (
            "========= Excitation energies and oscillator strengths =========\n"
            "State    1 : E =    3.8474 eV     322.276 nm      31032.13 cm-1\n"
            "E(TD) =   -55.650000000      <S**2>= 0.000     f=  0.1234\n"
            "Error occured in dpotrf!\n"
        )
    (workdir / aop_name).write_text(aop_text, encoding="utf-8")
    return subprocess.CompletedProcess(cmd, 0, stdout="partial\n", stderr="")


class _FakePopenWithHeartbeat:
    def __init__(self, cmd, cwd, env, stdout, stderr, text):
        del env, stdout, stderr, text
        self._cmd = cmd
        self._workdir = Path(cwd)
        self._aop_path = self._workdir / Path(cmd[2]).name
        self.pid = 4321
        self._poll_count = 0

    def poll(self):
        self._poll_count += 1
        if self._poll_count == 1:
            self._aop_path.write_text("SCF iteration in progress\n", encoding="utf-8")
            return None
        label = Path(self._cmd[1]).stem
        if label.endswith("_s0"):
            self._aop_path.write_text(S0_AOP_TEXT, encoding="utf-8")
        else:
            self._aop_path.write_text(S1_AOP_TEXT, encoding="utf-8")
        (self._workdir / f"{label}.mo").write_text("fake mo\n", encoding="utf-8")
        return 0


def test_amesp_baseline_tool_executes_fake_s0_and_s1_pipeline(tmp_path: Path) -> None:
    amesp_bin = tmp_path / "amesp"
    amesp_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    progress_events: list[dict[str, object]] = []
    tool = AmespBaselineMicroscopicTool(
        amesp_bin=amesp_bin,
        structure_preparer=_fake_structure_preparer,
        subprocess_runner=_fake_subprocess_success,
    )

    result = tool.execute(
        plan=MicroscopicExecutionPlan(
            local_goal="Run baseline S0/S1 Amesp workflow.",
            requested_deliverables=["S0 geometry optimization", "S1 vertical excitation characterization"],
            microscopic_tool_request=MicroscopicToolRequest(
                capability_name="run_baseline_bundle",
                perform_new_calculation=True,
                deliverables=["S0 geometry optimization", "S1 vertical excitation characterization"],
                state_window=[1, 2],
                requested_route_summary="Test baseline bundle request.",
            ),
            structure_source="prepared_from_smiles",
            failure_reporting="Return a partial or failed local report if Amesp fails.",
        ),
        smiles="N",
        label="fake_case",
        workdir=tmp_path / "workdir",
        available_artifacts={},
        progress_callback=progress_events.append,
        round_index=1,
        case_id="case123",
        current_hypothesis="restriction of intramolecular motion (RIM)-dominated AIE",
    )

    assert result.s0.final_energy_hartree == -55.7914717877
    assert result.s0.homo_lumo_gap_ev == 13.991547
    assert len(result.s0.mulliken_charges) == 4
    assert result.s1.first_excitation_energy_ev == 3.8474
    assert result.s1.first_oscillator_strength == 0.1234
    assert result.s1.state_count == 2
    assert result.s1.excited_states[0].dominant_transitions == [
        {"occupied_orbital": 4, "virtual_orbital": 5, "coefficient": 0.81234}
    ]
    assert result.route == "baseline_bundle"
    assert result.executed_capability == "run_baseline_bundle"
    assert result.performed_new_calculations is True
    assert result.route_summary["state_count"] == 2
    assert result.route_summary["first_bright_state_index"] == 1
    assert "prepared_xyz_path" in result.generated_artifacts
    assert Path(result.generated_artifacts["s0_aop_path"]).exists()
    assert Path(result.generated_artifacts["s1_aop_path"]).exists()
    assert any(
        event["phase"] == "probe"
        and event["details"].get("probe_stage") == "structure_prep"
        and event["details"].get("probe_status") == "end"
        for event in progress_events
    )
    assert any(
        event["phase"] == "probe"
        and event["details"].get("probe_stage") == "s0_optimization"
        and event["details"].get("probe_status") == "end"
        for event in progress_events
    )
    assert any(
        event["phase"] == "probe"
        and event["details"].get("probe_stage") == "s1_vertical_excitation"
        and event["details"].get("probe_status") == "end"
        for event in progress_events
    )


def test_amesp_baseline_tool_injects_amesp_bin_dir_into_subprocess_path(tmp_path: Path) -> None:
    captured_inputs: dict[str, str] = {}
    captured_envs: dict[str, dict[str, str]] = {}
    amesp_bin_dir = tmp_path / "amesp-bin"
    amesp_bin_dir.mkdir(parents=True, exist_ok=True)
    amesp_bin = amesp_bin_dir / "amesp"
    amesp_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    tool = AmespBaselineMicroscopicTool(
        amesp_bin=amesp_bin,
        structure_preparer=_fake_structure_preparer,
        subprocess_runner=_build_fake_subprocess_with_env_capture(captured_inputs, captured_envs),
    )

    tool.execute(
        plan=MicroscopicExecutionPlan(
            local_goal="Run baseline S0/S1 Amesp workflow.",
            requested_deliverables=["S0 geometry optimization", "S1 vertical excitation characterization"],
            microscopic_tool_request=MicroscopicToolRequest(
                capability_name="run_baseline_bundle",
                perform_new_calculation=True,
                deliverables=["S0 geometry optimization", "S1 vertical excitation characterization"],
                state_window=[1, 2],
                requested_route_summary="Test baseline bundle request.",
            ),
            structure_source="prepared_from_smiles",
            failure_reporting="Return a partial or failed local report if Amesp fails.",
        ),
        smiles="N",
        label="fake_case_env",
        workdir=tmp_path / "workdir_env",
        available_artifacts={},
        round_index=1,
    )

    s0_env = captured_envs["fake_case_env_s0"]
    assert s0_env["PATH"].split(os.pathsep)[0] == str(amesp_bin_dir)
    assert str(amesp_bin_dir) in s0_env["PATH"].split(os.pathsep)


def test_parse_excited_states_prefers_reported_excitation_energy_over_total_energy_difference() -> None:
    from aie_mas.tools.amesp import _parse_excited_states

    text = """
========= Excitation energies and oscillator strengths =========
State    1 : E =    3.0587 eV     405.350 nm      24669.99 cm-1
E(TD) =  -2708.578180955      <S**2>= 0.000     f=  1.0346
"""

    states = _parse_excited_states(
        text,
        reference_energy_hartree=-123.2527000504,
    )

    assert len(states) == 1
    assert states[0].state_index == 1
    assert states[0].total_energy_hartree == -2708.578180955
    assert states[0].oscillator_strength == 1.0346
    assert states[0].spin_square == 0.0
    assert states[0].excitation_energy_ev == 3.0587


def test_amesp_execute_wraps_radical_structure_prep_error_as_precondition_failure(tmp_path: Path) -> None:
    amesp_bin = tmp_path / "amesp"
    amesp_bin.write_text("#!/bin/sh\n", encoding="utf-8")

    def _radical_structure_preparer(request):
        raise StructurePrepError(
            "unsupported_radical",
            "Only closed-shell molecules are supported in the first version; radical electrons were detected.",
        )

    progress_events: list[dict[str, object]] = []
    tool = AmespBaselineMicroscopicTool(
        amesp_bin=amesp_bin,
        structure_preparer=_radical_structure_preparer,
        subprocess_runner=_fake_subprocess_success,
    )

    try:
        tool.execute(
            plan=MicroscopicExecutionPlan(
                local_goal="Attempt baseline execution for a radical molecule.",
                requested_deliverables=["S0 geometry optimization"],
                microscopic_tool_request=MicroscopicToolRequest(
                    capability_name="run_baseline_bundle",
                    perform_new_calculation=True,
                    deliverables=["S0 geometry optimization"],
                    requested_route_summary="Test structure-prep precondition handling.",
                ),
                structure_source="prepared_from_smiles",
                failure_reporting="Return failed if structure preparation cannot produce a supported molecule.",
            ),
            smiles="[CH3]",
            label="radical_case",
            workdir=tmp_path / "radical_case_workdir",
            available_artifacts={},
            progress_callback=lambda event: progress_events.append(event),
            round_index=1,
            case_id="radical_case",
            current_hypothesis="neutral aromatic",
        )
    except AmespExecutionError as exc:
        assert exc.code == "precondition_missing"
        assert "Structure preparation failed" in exc.message
        assert exc.raw_results["structure_prep_error"]["code"] == "unsupported_radical"
        assert exc.structured_results["structure_prep_error"]["message"].endswith("radical electrons were detected.")
    else:  # pragma: no cover
        raise AssertionError("Expected structure preparation failure to be wrapped as a precondition error.")

    assert any(
        event["phase"] == "probe"
        and event["details"].get("probe_stage") == "structure_prep"
        and event["details"].get("probe_status") == "failed"
        and event["details"].get("error", {}).get("code") == "unsupported_radical"
        for event in progress_events
    )


def test_amesp_baseline_tool_writes_parallel_ricosx_and_fast_td_defaults(tmp_path: Path) -> None:
    amesp_bin = tmp_path / "amesp"
    amesp_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    captured_inputs: dict[str, str] = {}
    tool = AmespBaselineMicroscopicTool(
        amesp_bin=amesp_bin,
        npara=20,
        maxcore_mb=12000,
        use_ricosx=True,
        s1_nstates=1,
        td_tout=1,
        structure_preparer=_fake_structure_preparer,
        subprocess_runner=_build_fake_subprocess_with_aip_capture(captured_inputs),
    )

    tool.execute(
        plan=MicroscopicExecutionPlan(
            local_goal="Run baseline S0/S1 Amesp workflow.",
            requested_deliverables=["S0 geometry optimization", "S1 vertical excitation characterization"],
            microscopic_tool_request=MicroscopicToolRequest(
                capability_name="run_baseline_bundle",
                perform_new_calculation=True,
                deliverables=["S0 geometry optimization", "S1 vertical excitation characterization"],
                state_window=[1],
                requested_route_summary="Test baseline bundle request.",
            ),
            structure_source="prepared_from_smiles",
            failure_reporting="Return a partial or failed local report if Amesp fails.",
        ),
        smiles="N",
        label="fast_case",
        workdir=tmp_path / "workdir",
        available_artifacts={},
    )

    s0_input = captured_inputs["fast_case_s0"]
    s1_input = captured_inputs["fast_case_s1"]

    assert "% npara 20" in s0_input
    assert "% maxcore 12000" in s0_input
    assert "! aTB1 opt force".lower() in s0_input.lower()
    assert ">opt" in s0_input
    assert "maxcyc 2000" in s0_input
    assert "gediis off" in s0_input
    assert "maxstep 0.3" in s0_input
    assert ">scf" in s0_input
    assert "vshift 500" in s0_input
    assert "! b3lyp sto-3g td RICOSX" in s1_input
    assert "nstates 1" in s1_input
    assert "tout 1" in s1_input


def test_amesp_baseline_tool_emits_subprocess_heartbeat_events(tmp_path: Path, monkeypatch) -> None:
    amesp_bin = tmp_path / "amesp"
    amesp_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    progress_events: list[dict[str, object]] = []
    monkeypatch.setattr("aie_mas.tools.amesp.time.sleep", lambda _: None)
    tool = AmespBaselineMicroscopicTool(
        amesp_bin=amesp_bin,
        npara=4,
        maxcore_mb=2000,
        use_ricosx=True,
        s1_nstates=1,
        td_tout=1,
        probe_interval_seconds=0.0,
        structure_preparer=_fake_structure_preparer,
        subprocess_popen_factory=_FakePopenWithHeartbeat,
    )

    tool.execute(
        plan=MicroscopicExecutionPlan(
            local_goal="Run baseline S0/S1 Amesp workflow.",
            requested_deliverables=["S0 geometry optimization", "S1 vertical excitation characterization"],
            microscopic_tool_request=MicroscopicToolRequest(
                capability_name="run_baseline_bundle",
                perform_new_calculation=True,
                deliverables=["S0 geometry optimization", "S1 vertical excitation characterization"],
                state_window=[1],
                requested_route_summary="Test baseline bundle request.",
            ),
            structure_source="prepared_from_smiles",
            failure_reporting="Return a partial or failed local report if Amesp fails.",
        ),
        smiles="N",
        label="heartbeat_case",
        workdir=tmp_path / "workdir",
        available_artifacts={},
        progress_callback=progress_events.append,
    )

    assert any(
        event["details"].get("probe_stage") == "s0_optimization_subprocess"
        and event["details"].get("probe_status") == "start"
        for event in progress_events
    )
    assert any(
        event["details"].get("probe_stage") == "s0_optimization_subprocess"
        and event["details"].get("probe_status") == "running"
        and event["details"].get("aop_tail") == "SCF iteration in progress"
        for event in progress_events
    )


def test_amesp_tool_creates_nested_route_workdir_before_writing_inputs(tmp_path: Path) -> None:
    amesp_bin = tmp_path / "amesp"
    amesp_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    tool = AmespBaselineMicroscopicTool(
        amesp_bin=amesp_bin,
        structure_preparer=_fake_structure_preparer,
        subprocess_runner=_fake_subprocess_success,
    )

    nested_workdir = tmp_path / "workdir" / "torsion_01"
    result = tool.execute(
        plan=MicroscopicExecutionPlan(
            local_goal="Run baseline S0/S1 Amesp workflow.",
            requested_deliverables=["S0 geometry optimization", "S1 vertical excitation characterization"],
            microscopic_tool_request=MicroscopicToolRequest(
                capability_name="run_baseline_bundle",
                perform_new_calculation=True,
                deliverables=["S0 geometry optimization", "S1 vertical excitation characterization"],
                state_window=[1, 2],
                requested_route_summary="Test baseline bundle request.",
            ),
            structure_source="prepared_from_smiles",
            failure_reporting="Return a partial or failed local report if Amesp fails.",
        ),
        smiles="N",
        label="nested_case",
        workdir=nested_workdir,
        available_artifacts={},
    )

    assert nested_workdir.exists()
    assert (nested_workdir / "nested_case_s0.aip").exists()
    assert Path(result.generated_artifacts["s0_aop_path"]).exists()


def test_amesp_torsion_capability_honors_structured_snapshot_parameters(
    tmp_path: Path, monkeypatch
) -> None:
    amesp_bin = tmp_path / "amesp"
    amesp_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    captured_inputs: dict[str, str] = {}
    monkeypatch.setattr("aie_mas.tools.amesp._generate_torsion_snapshot_bundle", _fake_torsion_snapshot_bundle)
    tool = AmespBaselineMicroscopicTool(
        amesp_bin=amesp_bin,
        structure_preparer=_fake_structure_preparer,
        subprocess_runner=_build_fake_subprocess_with_aip_capture(captured_inputs),
        follow_up_max_torsion_snapshots_total=6,
    )

    result = tool.execute(
        plan=MicroscopicExecutionPlan(
            local_goal="Run an exact two-point torsion follow-up.",
            requested_deliverables=["torsion sensitivity summary", "per-snapshot excitation records"],
            capability_route="torsion_snapshot_follow_up",
                microscopic_tool_request=MicroscopicToolRequest(
                    capability_name="run_torsion_snapshots",
                    perform_new_calculation=True,
                    artifact_scope="torsion_snapshots",
                    dihedral_id="dih_0_1_2_3",
                    dihedral_atom_indices=[0, 1, 2, 3],
                    snapshot_count=2,
                    angle_offsets_deg=[25.0, -25.0],
                    state_window=[1, 2, 3],
                deliverables=["torsion sensitivity summary", "per-snapshot excitation records"],
                requested_route_summary="Use exactly two torsion snapshots at ±25 degrees.",
            ),
            structure_source="prepared_from_smiles",
            failure_reporting="Return partial or failed if Amesp fails.",
        ),
        smiles="N",
        label="torsion_case",
        workdir=tmp_path / "torsion_workdir",
        available_artifacts={},
    )

    assert result.executed_capability == "run_torsion_snapshots"
    assert result.performed_new_calculations is True
    assert result.resolved_target_ids["dihedral_id"] == "dih_0_1_2_3"
    assert len(result.route_records) == 2
    assert result.generated_artifacts["torsion_snapshot_count"] == 2
    assert [record["target_angle_deg"] for record in result.route_records] == [25.0, -25.0]
    assert all(record["dihedral_atoms"] == [0, 1, 2, 3] for record in result.route_records)
    assert len(result.generated_artifacts["snapshot_artifacts"]) == 2


def test_amesp_torsion_capability_can_skip_ground_state_reoptimization(
    tmp_path: Path,
    monkeypatch,
) -> None:
    amesp_bin = tmp_path / "amesp"
    amesp_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    progress_events: list[dict[str, object]] = []
    monkeypatch.setattr("aie_mas.tools.amesp._generate_torsion_snapshot_bundle", _fake_torsion_snapshot_bundle)
    tool = AmespBaselineMicroscopicTool(
        amesp_bin=amesp_bin,
        structure_preparer=_fake_structure_preparer,
        subprocess_runner=_fake_subprocess_success,
        follow_up_max_torsion_snapshots_total=6,
    )

    result = tool.execute(
        plan=MicroscopicExecutionPlan(
            local_goal="Run a no-reoptimization torsion follow-up.",
            requested_deliverables=["torsion sensitivity summary", "per-snapshot excitation records"],
            capability_route="torsion_snapshot_follow_up",
            microscopic_tool_request=MicroscopicToolRequest(
                capability_name="run_torsion_snapshots",
                perform_new_calculation=True,
                optimize_ground_state=False,
                artifact_scope="torsion_snapshots",
                dihedral_id="dih_0_1_2_3",
                dihedral_atom_indices=[0, 1, 2, 3],
                snapshot_count=2,
                angle_offsets_deg=[25.0, -25.0],
                state_window=[1, 2, 3],
                deliverables=["torsion sensitivity summary", "per-snapshot excitation records"],
                requested_route_summary="Use exactly two torsion snapshots at ±25 degrees without geometry re-optimization.",
            ),
            structure_source="prepared_from_smiles",
            failure_reporting="Return partial or failed if Amesp fails.",
        ),
        smiles="N",
        label="torsion_no_reopt_case",
        workdir=tmp_path / "torsion_no_reopt_workdir",
        available_artifacts={},
        progress_callback=progress_events.append,
    )

    assert result.executed_capability == "run_torsion_snapshots"
    assert result.honored_constraints[-1] == "Execution request honored `optimize_ground_state=false` and skipped geometry re-optimization."
    assert any(
        event["details"].get("probe_stage") == "s0_singlepoint_subprocess"
        for event in progress_events
    )
    assert not any(
        event["details"].get("probe_stage") == "s0_optimization_subprocess"
        for event in progress_events
    )


def test_amesp_targeted_state_characterization_reuses_torsion_bundle_with_bounded_follow_up(
    tmp_path: Path,
    monkeypatch,
) -> None:
    tool = _build_targeted_follow_up_tool(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        subprocess_runner=_fake_subprocess_success,
    )
    torsion_result = _run_torsion_source_bundle(tool=tool, tmp_path=tmp_path)
    targeted_result = _run_targeted_property_follow_up(
        tool=tool,
        tmp_path=tmp_path,
        torsion_result=torsion_result,
        capability_name="run_targeted_state_characterization",
        deliverables=[
            "targeted state-characterization records",
            "state-family overlap summary",
            "bounded CT/state-character proxy summary",
        ],
        descriptor_scope=[
            "dominant_transitions",
            "state_family_overlap",
            "ground_state_dipole",
            "mulliken_charges",
            "molecular_orbital_files",
        ],
    )

    assert targeted_result.executed_capability == "run_targeted_state_characterization"
    assert targeted_result.route == "targeted_property_follow_up"
    assert targeted_result.performed_new_calculations is True
    assert targeted_result.reused_existing_artifacts is True
    assert (
        "Execution request honored `optimize_ground_state=false` and skipped geometry re-optimization."
        in targeted_result.honored_constraints
    )
    assert len(targeted_result.route_records) == 2
    assert len(targeted_result.parsed_snapshot_records) == 2
    assert targeted_result.route_summary["artifact_scope"] == "torsion_snapshots"
    assert targeted_result.route_summary["artifact_source_round"] == 2
    assert targeted_result.route_summary["selected_target_count"] == 2
    assert set(targeted_result.route_summary["selected_target_members"]) == {"torsion_01", "torsion_02"}
    assert targeted_result.route_summary["state_characterization_availability"] == "proxy_only"
    assert "state_family_overlap" in targeted_result.route_summary["available_state_character_descriptors"]
    assert "dominant_transitions" in targeted_result.route_summary["available_state_character_descriptors"]
    assert "ground_state_dipole" in targeted_result.route_summary["available_state_character_descriptors"]
    assert targeted_result.route_summary["shared_first_state_virtual_orbitals"] == [5]
    assert targeted_result.route_summary["shared_first_bright_state_virtual_orbitals"] == [5]
    assert targeted_result.missing_deliverables == []
    assert targeted_result.generated_artifacts["artifact_bundle_id"] == "round_04_run_targeted_state_characterization_bundle"
    assert targeted_result.generated_artifacts["artifact_bundle_kind"] == "targeted_property_follow_up"
    assert targeted_result.generated_artifacts["selected_target_count"] == 2
    assert len(targeted_result.generated_artifacts["characterization_artifacts"]) == 2
    assert len(targeted_result.generated_artifacts["reused_snapshot_artifacts"]) == 2
    registry_entries = list(targeted_result.generated_artifacts.get("artifact_bundle_registry_entries") or [])
    assert len(registry_entries) == 1
    assert registry_entries[0]["artifact_bundle"]["bundle_id"] == "round_04_run_targeted_state_characterization_bundle"
    assert registry_entries[0]["artifact_bundle"]["bundle_kind"] == "targeted_property_follow_up"
    assert registry_entries[0]["artifact_bundle"]["source_bundle_id"] == "round_02_torsion_snapshots"
    assert registry_entries[0]["artifact_bundle"]["source_member_ids"] == ["torsion_01", "torsion_02"]
    assert [member["member_id"] for member in registry_entries[0]["bundle_members"]] == ["torsion_01", "torsion_02"]

    first_record = targeted_result.route_records[0]
    assert first_record["state_family_overlap"]["available"] is True
    assert "state_family_overlap" in first_record["available_state_character_descriptors"]
    assert "ground_state_dipole" in first_record["available_state_character_descriptors"]
    assert "mulliken_charges" in first_record["available_state_character_descriptors"]
    assert "molecular_orbital_files" in first_record["available_state_character_descriptors"]
    assert first_record["molecular_orbital_files_available"] is True


def test_amesp_targeted_follow_up_supports_exact_member_targeting(
    tmp_path: Path,
    monkeypatch,
) -> None:
    tool = _build_targeted_follow_up_tool(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        subprocess_runner=_fake_subprocess_success,
    )
    torsion_result = _run_torsion_source_bundle(tool=tool, tmp_path=tmp_path)

    result = tool.execute(
        plan=MicroscopicExecutionPlan(
            local_goal="Reuse one exact torsion member for targeted follow-up.",
            requested_deliverables=["targeted state-characterization records"],
            capability_route="targeted_property_follow_up",
            microscopic_tool_request=MicroscopicToolRequest(
                capability_name="run_targeted_state_characterization",
                perform_new_calculation=True,
                optimize_ground_state=False,
                artifact_bundle_id="round_02_torsion_snapshots",
                artifact_source_round=2,
                artifact_scope="torsion_snapshots",
                artifact_member_ids=["torsion_02"],
                target_selection_mode="exact_members",
                state_window=[1, 2, 3],
                target_count=2,
                deliverables=["targeted state-characterization records"],
                requested_route_summary="Reuse exactly torsion_02 for targeted follow-up.",
            ),
            structure_source="existing_prepared_structure",
            failure_reporting="Return partial or failed if Amesp fails.",
        ),
        smiles="N",
        label="exact_member_target",
        workdir=tmp_path / "exact_member_target_workdir",
        available_artifacts={**torsion_result.generated_artifacts, "source_round": 2},
        round_index=4,
    )

    assert result.route_summary["target_selection_mode"] == "exact_members"
    assert result.route_summary["requested_exact_member_ids"] == ["torsion_02"]
    assert result.route_summary["selected_target_count"] == 1
    assert result.route_summary["selected_target_members"] == ["torsion_02"]
    assert len(result.route_records) == 1
    assert result.route_records[0]["member_id"] == "torsion_02"


def test_amesp_list_artifact_bundle_members_returns_stable_member_metadata(
    tmp_path: Path,
    monkeypatch,
) -> None:
    tool = _build_targeted_follow_up_tool(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        subprocess_runner=_fake_subprocess_success,
    )
    torsion_result = _run_torsion_source_bundle(tool=tool, tmp_path=tmp_path)

    result = tool.execute(
        plan=MicroscopicExecutionPlan(
            local_goal="List stable member ids for one reusable torsion bundle.",
            requested_deliverables=["artifact bundle member inventory"],
            capability_route="artifact_parse_only",
            microscopic_tool_plan=MicroscopicToolPlan(
                calls=[
                    MicroscopicToolCall(
                        call_id="discover_artifact_bundle_members",
                        call_kind="discovery",
                        request=MicroscopicToolRequest(
                            capability_name="list_artifact_bundle_members",
                            artifact_bundle_id="round_02_torsion_snapshots",
                            artifact_kind="torsion_snapshots",
                            perform_new_calculation=False,
                            reuse_existing_artifacts_only=True,
                            requested_route_summary="List stable members for one torsion bundle.",
                        ),
                    )
                ],
                requested_route_summary="List stable members for one torsion bundle.",
                requested_deliverables=["artifact bundle member inventory"],
                selection_policy=SelectionPolicy(artifact_kind="torsion_snapshots", source_round_preference=2),
            ),
            microscopic_tool_request=MicroscopicToolRequest(
                capability_name="list_artifact_bundle_members",
                artifact_bundle_id="round_02_torsion_snapshots",
                artifact_kind="torsion_snapshots",
                perform_new_calculation=False,
                reuse_existing_artifacts_only=True,
                deliverables=["artifact bundle member inventory"],
                requested_route_summary="List stable members for one torsion bundle.",
            ),
            structure_source="existing_prepared_structure",
            failure_reporting="Return partial or failed if discovery fails.",
        ),
        smiles="N",
        label="list_artifact_bundle_members",
        workdir=tmp_path / "list_artifact_bundle_members_workdir",
        available_artifacts={**torsion_result.generated_artifacts, "source_round": 2},
        round_index=4,
    )

    assert result.executed_capability == "list_artifact_bundle_members"
    assert result.performed_new_calculations is False
    assert result.reused_existing_artifacts is True
    assert result.route_summary["discovery_capability"] == "list_artifact_bundle_members"
    assert result.route_summary["item_count"] == 2
    assert [record["member_id"] for record in result.route_records] == ["torsion_01", "torsion_02"]
    assert result.route_records[0]["source_bundle_id"] == "round_02_torsion_snapshots"
    assert "inspect_raw_artifact_bundle" in result.route_records[0]["parse_capabilities_supported"]


def test_amesp_targeted_charge_analysis_writes_hirshfeld_and_returns_charge_records(
    tmp_path: Path,
    monkeypatch,
) -> None:
    captured_inputs: dict[str, str] = {}
    tool = _build_targeted_follow_up_tool(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        subprocess_runner=_build_fake_subprocess_with_targeted_analysis_capture(captured_inputs),
    )
    torsion_result = _run_torsion_source_bundle(tool=tool, tmp_path=tmp_path)
    result = _run_targeted_property_follow_up(
        tool=tool,
        tmp_path=tmp_path,
        torsion_result=torsion_result,
        capability_name="run_targeted_charge_analysis",
        deliverables=[
            "targeted charge-analysis records",
            "charge availability summary",
            "bounded raw charge observables",
        ],
    )

    assert result.executed_capability == "run_targeted_charge_analysis"
    assert result.route == "targeted_property_follow_up"
    assert result.route_summary["charge_availability"] == "proxy_only"
    assert "hirshfeld_charges" in result.route_summary["available_charge_observables"]
    assert "ground_state_dipole" in result.route_summary["available_charge_observables"]
    assert "mulliken_charges" not in result.route_summary["available_charge_observables"]
    assert result.route_summary["missing_charge_observables"] == []
    first_record = result.route_records[0]
    assert first_record["charge_analysis"]["charge_scheme"] == "hirshfeld"
    assert first_record["charge_analysis"]["charge_availability"] == "available"
    assert len(first_record["charge_analysis"]["charge_table"]) == 4
    assert "charge hirshfeld" in captured_inputs["run_targeted_charge_analysis_follow_up_torsion_01_char_s0sp"]


def test_amesp_targeted_localized_orbital_analysis_writes_method_lmo_and_returns_records(
    tmp_path: Path,
    monkeypatch,
) -> None:
    captured_inputs: dict[str, str] = {}
    tool = _build_targeted_follow_up_tool(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        subprocess_runner=_build_fake_subprocess_with_targeted_analysis_capture(captured_inputs),
    )
    torsion_result = _run_torsion_source_bundle(tool=tool, tmp_path=tmp_path)
    result = _run_targeted_property_follow_up(
        tool=tool,
        tmp_path=tmp_path,
        torsion_result=torsion_result,
        capability_name="run_targeted_localized_orbital_analysis",
        deliverables=[
            "targeted localized-orbital analysis records",
            "localized-orbital availability summary",
            "bounded raw localized-orbital observables",
        ],
    )

    assert result.executed_capability == "run_targeted_localized_orbital_analysis"
    assert result.route_summary["localized_orbital_availability"] == "proxy_only"
    assert "localized_orbitals_pm" in result.route_summary["available_localized_orbital_observables"]
    assert "molecular_orbital_files" in result.route_summary["available_localized_orbital_observables"]
    first_record = result.route_records[0]
    assert first_record["localized_orbital_analysis"]["localization_method"] == "pm"
    assert first_record["localized_orbital_analysis"]["localized_orbitals_available"] is True
    assert result.generated_artifacts["artifact_bundle_id"] == "round_04_run_targeted_localized_orbital_analysis_bundle"
    assert result.generated_artifacts["artifact_bundle_kind"] == "targeted_property_follow_up"
    s0_input = captured_inputs["run_targeted_localized_orbital_analysis_follow_up_torsion_01_char_s0sp"]
    assert ">method" in s0_input
    assert "lmo pm" in s0_input
    assert ">ope" in s0_input
    assert "mofile on" in s0_input


def test_amesp_targeted_natural_orbital_analysis_writes_method_natorb_and_returns_records(
    tmp_path: Path,
    monkeypatch,
) -> None:
    captured_inputs: dict[str, str] = {}
    tool = _build_targeted_follow_up_tool(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        subprocess_runner=_build_fake_subprocess_with_targeted_analysis_capture(captured_inputs),
    )
    torsion_result = _run_torsion_source_bundle(tool=tool, tmp_path=tmp_path)
    result = _run_targeted_property_follow_up(
        tool=tool,
        tmp_path=tmp_path,
        torsion_result=torsion_result,
        capability_name="run_targeted_natural_orbital_analysis",
        deliverables=[
            "targeted natural-orbital analysis records",
            "natural-orbital availability summary",
            "bounded raw natural-orbital observables",
        ],
    )

    assert result.executed_capability == "run_targeted_natural_orbital_analysis"
    assert result.route_summary["natural_orbital_availability"] == "proxy_only"
    assert "natural_orbitals_no" in result.route_summary["available_natural_orbital_observables"]
    assert "molecular_orbital_files" in result.route_summary["available_natural_orbital_observables"]
    first_record = result.route_records[0]
    assert first_record["natural_orbital_analysis"]["natural_orbital_kind"] == "no"
    assert first_record["natural_orbital_analysis"]["natural_orbitals_available"] is True
    assert result.generated_artifacts["artifact_bundle_id"] == "round_04_run_targeted_natural_orbital_analysis_bundle"
    assert result.generated_artifacts["artifact_bundle_kind"] == "targeted_property_follow_up"
    s0_input = captured_inputs["run_targeted_natural_orbital_analysis_follow_up_torsion_01_char_s0sp"]
    assert ">method" in s0_input
    assert "natorb no" in s0_input
    assert ">ope" in s0_input
    assert "mofile on" in s0_input


def test_amesp_targeted_density_population_analysis_writes_out2_and_returns_density_population_records(
    tmp_path: Path,
    monkeypatch,
) -> None:
    captured_inputs: dict[str, str] = {}
    tool = _build_targeted_follow_up_tool(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        subprocess_runner=_build_fake_subprocess_with_targeted_analysis_capture(captured_inputs),
    )
    torsion_result = _run_torsion_source_bundle(tool=tool, tmp_path=tmp_path)
    result = _run_targeted_property_follow_up(
        tool=tool,
        tmp_path=tmp_path,
        torsion_result=torsion_result,
        capability_name="run_targeted_density_population_analysis",
        deliverables=[
            "targeted density/population analysis records",
            "density/population availability summary",
            "bounded raw density/population observables",
        ],
    )

    assert result.route_summary["density_population_availability"] == "proxy_only"
    assert set(result.route_summary["available_density_population_observables"]) == {
        "density_matrix",
        "gross_orbital_populations",
        "mayer_bond_order",
    }
    first_record = result.route_records[0]
    density_record = first_record["density_population_analysis"]
    assert density_record["density_matrix_available"] is True
    assert density_record["gross_orbital_populations_available"] is True
    assert density_record["mayer_bond_order_available"] is True
    assert density_record["top_mayer_pairs"][0]["bond_order"] == 0.91
    assert result.generated_artifacts["artifact_bundle_id"] == "round_04_run_targeted_density_population_analysis_bundle"
    assert result.generated_artifacts["artifact_bundle_kind"] == "targeted_property_follow_up"
    assert "out 2" in captured_inputs["run_targeted_density_population_analysis_follow_up_torsion_01_char_s0sp"]


def test_amesp_targeted_transition_dipole_analysis_writes_tda_atb_excdip_and_returns_transition_dipole_records(
    tmp_path: Path,
    monkeypatch,
) -> None:
    captured_inputs: dict[str, str] = {}
    tool = _build_targeted_follow_up_tool(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        subprocess_runner=_build_fake_subprocess_with_targeted_analysis_capture(captured_inputs),
    )
    torsion_result = _run_torsion_source_bundle(tool=tool, tmp_path=tmp_path)
    result = _run_targeted_property_follow_up(
        tool=tool,
        tmp_path=tmp_path,
        torsion_result=torsion_result,
        capability_name="run_targeted_transition_dipole_analysis",
        deliverables=[
            "targeted transition-dipole analysis records",
            "transition-dipole availability summary",
            "bounded raw transition-dipole observables",
        ],
    )

    assert result.executed_capability == "run_targeted_transition_dipole_analysis"
    assert result.route == "targeted_property_follow_up"
    assert result.route_summary["transition_dipole_availability"] == "proxy_only"
    assert set(result.route_summary["available_transition_dipole_observables"]) == {
        "ground_to_excited_transition_dipoles",
        "excited_to_excited_transition_dipoles",
    }
    first_record = result.route_records[0]
    assert first_record["transition_dipole_method"] == "tda-aTB1-excdip"
    assert len(first_record["ground_to_excited_transition_dipoles"]) == 2
    assert len(first_record["excited_to_excited_transition_dipoles"]) == 2
    assert first_record["transition_dipole_section_presence"]["ground_to_excited_section_present"] is True
    assert first_record["transition_dipole_section_presence"]["excited_to_excited_section_present"] is True
    s1_input = captured_inputs["run_targeted_transition_dipole_analysis_follow_up_torsion_01_char_s1"].lower()
    assert "! atb1 tda" in s1_input
    assert ">atb" in s1_input
    assert "excdip on" in s1_input


def test_amesp_targeted_approx_delta_dipole_analysis_returns_proxy_records(
    tmp_path: Path,
    monkeypatch,
) -> None:
    captured_inputs: dict[str, str] = {}
    tool = _build_targeted_follow_up_tool(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        subprocess_runner=_build_fake_subprocess_with_approx_dipole_capture(captured_inputs),
    )
    torsion_result = _run_torsion_source_bundle(tool=tool, tmp_path=tmp_path)
    result = _run_targeted_property_follow_up(
        tool=tool,
        tmp_path=tmp_path,
        torsion_result=torsion_result,
        capability_name="run_targeted_approx_delta_dipole_analysis",
        deliverables=[
            "targeted approximate dipole-change analysis records",
            "approximate dipole-change availability summary",
            "bounded approximate per-atom-charge-derived dipole proxy observables",
        ],
    )

    assert result.executed_capability == "run_targeted_approx_delta_dipole_analysis"
    assert result.route == "targeted_property_follow_up"
    assert result.route_summary["approx_delta_dipole_availability"] == "proxy_only"
    assert set(result.route_summary["available_approx_delta_dipole_observables"]) == {
        "approx_ground_state_dipole",
        "approx_excited_state_dipole",
        "approx_delta_dipole_same_geometry_ground_ref",
        "approx_delta_dipole_same_geometry_excited_ref",
        "approx_delta_dipole_relaxed_total",
        "ground_state_atomic_charges",
        "excited_state_atomic_charges",
        "atom_order_alignment_status",
        "geometry_rmsd_angstrom",
    }
    first_record = result.route_records[0]
    assert first_record["atom_order_alignment_status"] == "aligned"
    assert first_record["approximate_dipole_proxy_note"].startswith(
        "approximate per-atom-charge-derived dipole proxy"
    )
    assert first_record["approx_ground_state_dipole"] is not None
    assert first_record["approx_excited_state_dipole"] is not None
    assert first_record["approx_delta_dipole_same_geometry_ground_ref"] is not None
    assert first_record["approx_delta_dipole_same_geometry_excited_ref"] is not None
    assert first_record["approx_delta_dipole_relaxed_total"] is not None
    assert first_record["geometry_rmsd_angstrom"] is not None
    assert result.generated_artifacts["artifact_bundle_id"] == (
        "round_04_run_targeted_approx_delta_dipole_analysis_bundle"
    )
    assert result.generated_artifacts["artifact_bundle_kind"] == "targeted_property_follow_up"
    s0_input = captured_inputs["run_targeted_approx_delta_dipole_analysis_follow_up_torsion_01_char_s0"]
    s1_input = captured_inputs["run_targeted_approx_delta_dipole_analysis_follow_up_torsion_01_char_s1"].lower()
    assert "! atb1 opt force" in s0_input.lower()
    assert "! atb1 tda opt force" in s1_input
    assert "root 1" in s1_input


def test_amesp_targeted_approx_delta_dipole_analysis_fails_on_atomic_order_mismatch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    captured_inputs: dict[str, str] = {}
    tool = _build_targeted_follow_up_tool(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        subprocess_runner=_build_fake_subprocess_with_approx_dipole_capture(
            captured_inputs,
            mismatch=True,
        ),
    )
    torsion_result = _run_torsion_source_bundle(tool=tool, tmp_path=tmp_path)

    with pytest.raises(AmespExecutionError) as excinfo:
        _run_targeted_property_follow_up(
            tool=tool,
            tmp_path=tmp_path,
            torsion_result=torsion_result,
            capability_name="run_targeted_approx_delta_dipole_analysis",
            deliverables=[
                "targeted approximate dipole-change analysis records",
                "approximate dipole-change availability summary",
                "bounded approximate per-atom-charge-derived dipole proxy observables",
            ],
        )

    assert excinfo.value.code == "parse_failed"
    assert "Atomic order mismatch" in excinfo.value.message
    assert excinfo.value.status == "failed"


def test_amesp_inspect_raw_artifact_bundle_supports_exact_member_targeting_for_follow_up_bundle(
    tmp_path: Path,
    monkeypatch,
) -> None:
    tool = _build_targeted_follow_up_tool(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        subprocess_runner=_fake_subprocess_success,
    )
    torsion_result = _run_torsion_source_bundle(tool=tool, tmp_path=tmp_path)
    localized_result = _run_targeted_property_follow_up(
        tool=tool,
        tmp_path=tmp_path,
        torsion_result=torsion_result,
        capability_name="run_targeted_localized_orbital_analysis",
        deliverables=[
            "targeted localized-orbital analysis records",
            "localized-orbital availability summary",
            "bounded raw localized-orbital observables",
        ],
    )

    inspect_result = tool.execute(
        plan=MicroscopicExecutionPlan(
            local_goal="Inspect one exact follow-up bundle member for raw localized-orbital artifacts.",
            requested_deliverables=[
                "raw artifact file inventory",
                "extractable observable inventory",
                "raw inspection notes",
            ],
            capability_route="artifact_parse_only",
            microscopic_tool_request=MicroscopicToolRequest(
                capability_name="inspect_raw_artifact_bundle",
                perform_new_calculation=False,
                reuse_existing_artifacts_only=True,
                artifact_bundle_id="round_04_run_targeted_localized_orbital_analysis_bundle",
                artifact_source_round=4,
                artifact_scope="targeted_property_follow_up",
                artifact_member_ids=["torsion_01"],
                target_selection_mode="exact_members",
                requested_observable_scope=["localized_orbitals_pm", "molecular_orbital_files"],
                deliverables=[
                    "raw artifact file inventory",
                    "extractable observable inventory",
                    "raw inspection notes",
                ],
                requested_route_summary="Inspect exactly torsion_01 from the localized-orbital follow-up bundle.",
            ),
            structure_source="existing_prepared_structure",
            failure_reporting="Return partial or failed if inspection fails.",
        ),
        smiles="N",
        label="localized_follow_up_inspect",
        workdir=tmp_path / "localized_follow_up_inspect_workdir",
        available_artifacts={**localized_result.generated_artifacts, "source_round": 4},
        round_index=5,
    )

    assert inspect_result.executed_capability == "inspect_raw_artifact_bundle"
    assert inspect_result.route == "artifact_parse_only"
    assert inspect_result.route_summary["artifact_scope"] == "targeted_property_follow_up"
    assert inspect_result.route_summary["target_selection_mode"] == "exact_members"
    assert inspect_result.route_summary["requested_exact_member_ids"] == ["torsion_01"]
    assert len(inspect_result.parsed_snapshot_records) == 1
    assert inspect_result.parsed_snapshot_records[0]["snapshot_label"] == "torsion_01"
    assert "localized_orbitals_pm" in inspect_result.route_summary["extractable_observables"]
    assert "molecular_orbital_files" in inspect_result.route_summary["extractable_observables"]
    assert inspect_result.missing_deliverables == []


def test_atb_reference_result_supports_approx_delta_dipole_when_reference_files_are_present() -> None:
    root = Path(__file__).resolve().parents[1] / "third_party" / "aTB" / "2"
    if not root.exists():
        pytest.skip("Local third_party/aTB reference fixture is not present in this checkout.")

    payload = json.loads((root / "result.json").read_text(encoding="utf-8"))
    ground_symbols, ground_coordinates = _read_xyz_symbols_and_coordinates(root / "opt" / "opted.xyz")
    excited_symbols, excited_coordinates = _read_xyz_symbols_and_coordinates(root / "excit" / "excited.xyz")
    ground_charge_elements = list(payload["ground_state"]["charge"]["element"])
    excited_charge_elements = list(payload["excited_state"]["charge"]["element"])
    ground_charge_values = [float(item) for item in payload["ground_state"]["charge"]["charge"]]
    excited_charge_values = [float(item) for item in payload["excited_state"]["charge"]["charge"]]

    assert ground_charge_elements == excited_charge_elements == ground_symbols == excited_symbols
    mu_s0 = _approximate_dipole_from_charges_and_coordinates(ground_charge_values, ground_coordinates)
    mu_s1 = _approximate_dipole_from_charges_and_coordinates(excited_charge_values, excited_coordinates)
    mu_s1_on_ground = _approximate_dipole_from_charges_and_coordinates(excited_charge_values, ground_coordinates)
    delta_same_geom = _approximate_delta_dipole(mu_s1_on_ground, mu_s0)

    assert mu_s0 is not None
    assert mu_s1 is not None
    assert delta_same_geom is not None
    assert round(mu_s0[3], 3) == 14.181
    assert round(mu_s1[3], 3) == 12.718
    assert round(delta_same_geom[3], 3) == 0.968


def test_amesp_ris_state_characterization_writes_tda_ris_and_returns_ris_state_character_records(
    tmp_path: Path,
    monkeypatch,
) -> None:
    captured_inputs: dict[str, str] = {}
    tool = _build_targeted_follow_up_tool(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        subprocess_runner=_build_fake_subprocess_with_targeted_analysis_capture(captured_inputs),
    )
    torsion_result = _run_torsion_source_bundle(tool=tool, tmp_path=tmp_path)
    result = _run_targeted_property_follow_up(
        tool=tool,
        tmp_path=tmp_path,
        torsion_result=torsion_result,
        capability_name="run_ris_state_characterization",
        deliverables=[
            "RIS state-characterization records",
            "RIS state-characterization availability summary",
            "bounded raw RIS state-character observables",
        ],
    )

    assert result.executed_capability == "run_ris_state_characterization"
    assert result.route == "targeted_property_follow_up"
    assert result.route_summary["ris_state_characterization_availability"] == "proxy_only"
    assert "state_family_overlap" in result.route_summary["available_ris_state_characterization_observables"]
    assert "dominant_transitions" in result.route_summary["available_ris_state_characterization_observables"]
    first_record = result.route_records[0]
    assert first_record["state_characterization_method"] == "tda-ris"
    assert first_record["state_family_overlap"]["available"] is True
    assert first_record["available_ris_state_characterization_observables"]
    s1_input = captured_inputs["run_ris_state_characterization_follow_up_torsion_01_char_s1"].lower()
    assert "! b3lyp sto-3g tda-ris" in s1_input


def test_amesp_parse_snapshot_outputs_reuses_existing_artifacts_without_new_calculations(
    tmp_path: Path, monkeypatch
) -> None:
    amesp_bin = tmp_path / "amesp"
    amesp_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    captured_inputs: dict[str, str] = {}
    monkeypatch.setattr("aie_mas.tools.amesp._generate_torsion_snapshot_bundle", _fake_torsion_snapshot_bundle)
    tool = AmespBaselineMicroscopicTool(
        amesp_bin=amesp_bin,
        structure_preparer=_fake_structure_preparer,
        subprocess_runner=_build_fake_subprocess_with_aip_capture(captured_inputs),
    )

    torsion_result = tool.execute(
        plan=MicroscopicExecutionPlan(
            local_goal="Generate bounded torsion snapshots for later parsing.",
            requested_deliverables=["torsion sensitivity summary"],
            capability_route="torsion_snapshot_follow_up",
                microscopic_tool_request=MicroscopicToolRequest(
                    capability_name="run_torsion_snapshots",
                    perform_new_calculation=True,
                    artifact_scope="torsion_snapshots",
                    dihedral_id="dih_0_1_2_3",
                    dihedral_atom_indices=[0, 1, 2, 3],
                    snapshot_count=2,
                    angle_offsets_deg=[25.0, -25.0],
                    state_window=[1, 2],
                deliverables=["torsion sensitivity summary"],
                requested_route_summary="Generate two torsion snapshots for later reuse.",
            ),
            structure_source="prepared_from_smiles",
            failure_reporting="Return partial or failed if Amesp fails.",
        ),
        smiles="N",
        label="parse_source",
        workdir=tmp_path / "parse_source_workdir",
        available_artifacts={},
        round_index=2,
    )
    input_count_before_parse = len(captured_inputs)

    parsed_result = tool.execute(
        plan=MicroscopicExecutionPlan(
            local_goal="Parse existing snapshot outputs only.",
            requested_deliverables=[
                "per-snapshot excitation records",
                "state-ordering summaries",
                "CT/localization proxy",
            ],
            capability_route="artifact_parse_only",
                microscopic_tool_request=MicroscopicToolRequest(
                    capability_name="parse_snapshot_outputs",
                    perform_new_calculation=False,
                    reuse_existing_artifacts_only=True,
                    artifact_bundle_id="round_02_torsion_snapshots",
                    artifact_source_round=2,
                    artifact_scope="torsion_snapshots",
                    state_window=[1, 2],
                deliverables=[
                    "per-snapshot excitation records",
                    "state-ordering summaries",
                    "CT/localization proxy",
                ],
                requested_route_summary="Reuse the existing torsion artifacts from round_02 without new calculations.",
            ),
            structure_source="existing_prepared_structure",
            failure_reporting="Return partial or failed if parsing fails.",
        ),
        smiles="N",
        label="parse_only",
        workdir=tmp_path / "parse_only_workdir",
        available_artifacts={**torsion_result.generated_artifacts, "source_round": 2},
        round_index=4,
    )

    assert parsed_result.executed_capability == "parse_snapshot_outputs"
    assert parsed_result.route == "artifact_parse_only"
    assert parsed_result.performed_new_calculations is False
    assert parsed_result.reused_existing_artifacts is True
    assert len(parsed_result.parsed_snapshot_records) == 2
    assert len(captured_inputs) == input_count_before_parse
    assert "CT/localization proxy" in parsed_result.missing_deliverables
    assert parsed_result.route_summary["ct_proxy_availability"] == "partial_observable_only"
    assert "dominant_transitions" in parsed_result.route_summary["available_ct_surrogates"]
    assert parsed_result.parsed_snapshot_records[0]["dominant_transitions"] != "not_available"


def test_amesp_parse_snapshot_outputs_reuses_baseline_bundle_artifacts_without_new_calculations(
    tmp_path: Path,
) -> None:
    amesp_bin = tmp_path / "amesp"
    amesp_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    tool = AmespBaselineMicroscopicTool(
        amesp_bin=amesp_bin,
        structure_preparer=_fake_structure_preparer,
        subprocess_runner=_fake_subprocess_success,
    )

    baseline_result = tool.execute(
        plan=MicroscopicExecutionPlan(
            local_goal="Generate the baseline bundle for later parse-only reuse.",
            requested_deliverables=["S0 optimized geometry", "vertical excited-state manifold"],
            capability_route="baseline_bundle",
            microscopic_tool_request=MicroscopicToolRequest(
                capability_name="run_baseline_bundle",
                perform_new_calculation=True,
                optimize_ground_state=True,
                state_window=[1, 2],
                deliverables=["S0 optimized geometry", "vertical excited-state manifold"],
                requested_route_summary="Run the default baseline bundle.",
            ),
            structure_source="prepared_from_smiles",
            failure_reporting="Return partial or failed if Amesp fails.",
        ),
        smiles="N",
        label="baseline_parse_source",
        workdir=tmp_path / "baseline_parse_source_workdir",
        available_artifacts={},
        round_index=2,
    )
    baseline_registry_entries = list(baseline_result.generated_artifacts.get("artifact_bundle_registry_entries") or [])
    assert len(baseline_registry_entries) == 1
    assert baseline_registry_entries[0]["artifact_bundle"]["bundle_id"] == "round_02_baseline_bundle"

    parsed_result = tool.execute(
        plan=MicroscopicExecutionPlan(
            local_goal="Parse the reusable baseline bundle without new calculations.",
            requested_deliverables=[
                "vertical excited-state manifold",
                "CT/localization proxy",
            ],
            capability_route="artifact_parse_only",
            microscopic_tool_request=MicroscopicToolRequest(
                capability_name="parse_snapshot_outputs",
                perform_new_calculation=False,
                reuse_existing_artifacts_only=True,
                artifact_bundle_id="round_02_baseline_bundle",
                artifact_source_round=2,
                artifact_scope="baseline_bundle",
                state_window=[1, 2],
                deliverables=[
                    "vertical excited-state manifold",
                    "CT/localization proxy",
                ],
                requested_route_summary="Reuse the existing baseline bundle without new calculations.",
            ),
            structure_source="existing_prepared_structure",
            failure_reporting="Return partial or failed if parsing fails.",
        ),
        smiles="N",
        label="baseline_parse_only",
        workdir=tmp_path / "baseline_parse_only_workdir",
        available_artifacts={**baseline_result.generated_artifacts, "source_round": 2},
        round_index=4,
    )

    assert parsed_result.executed_capability == "parse_snapshot_outputs"
    assert parsed_result.route == "artifact_parse_only"
    assert parsed_result.performed_new_calculations is False
    assert parsed_result.reused_existing_artifacts is True


def test_amesp_parse_snapshot_outputs_rejects_exact_member_targeting(
    tmp_path: Path,
    monkeypatch,
) -> None:
    tool = _build_targeted_follow_up_tool(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        subprocess_runner=_fake_subprocess_success,
    )
    torsion_result = _run_torsion_source_bundle(tool=tool, tmp_path=tmp_path)

    try:
        tool.execute(
            plan=MicroscopicExecutionPlan(
                local_goal="Attempt unsupported exact-member parse-only targeting.",
                requested_deliverables=["per-snapshot excitation records"],
                capability_route="artifact_parse_only",
                microscopic_tool_request=MicroscopicToolRequest(
                    capability_name="parse_snapshot_outputs",
                    perform_new_calculation=False,
                    reuse_existing_artifacts_only=True,
                    artifact_bundle_id="round_02_torsion_snapshots",
                    artifact_source_round=2,
                    artifact_scope="torsion_snapshots",
                    artifact_member_ids=["torsion_01"],
                    target_selection_mode="exact_members",
                    state_window=[1, 2],
                    deliverables=["per-snapshot excitation records"],
                    requested_route_summary="Attempt exact-member parse-only targeting.",
                ),
                structure_source="existing_prepared_structure",
                failure_reporting="Return partial or failed if parsing fails.",
            ),
            smiles="N",
            label="parse_exact_member_rejected",
            workdir=tmp_path / "parse_exact_member_rejected_workdir",
            available_artifacts={**torsion_result.generated_artifacts, "source_round": 2},
            round_index=4,
        )
    except AmespExecutionError as exc:
        assert exc.structured_results["completion_reason_code"] == "unsupported_target_selection_mode"
        assert exc.structured_results["unsupported_target_selection_mode"] == "exact_members"
        assert exc.structured_results["supported_target_selection_modes"] == ["bundle_wide"]
    else:
        raise AssertionError("Expected unsupported_target_selection_mode for exact-member parse-only request.")


def test_amesp_extract_ct_descriptors_from_bundle_reuses_baseline_bundle_artifacts(
    tmp_path: Path,
) -> None:
    amesp_bin = tmp_path / "amesp"
    amesp_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    tool = AmespBaselineMicroscopicTool(
        amesp_bin=amesp_bin,
        structure_preparer=_fake_structure_preparer,
        subprocess_runner=_fake_subprocess_success,
    )

    baseline_result = tool.execute(
        plan=MicroscopicExecutionPlan(
            local_goal="Generate a baseline bundle for later CT-descriptor extraction.",
            requested_deliverables=["S0 optimized geometry", "vertical excited-state manifold"],
            capability_route="baseline_bundle",
            microscopic_tool_request=MicroscopicToolRequest(
                capability_name="run_baseline_bundle",
                perform_new_calculation=True,
                optimize_ground_state=True,
                state_window=[1, 2],
                deliverables=["S0 optimized geometry", "vertical excited-state manifold"],
                requested_route_summary="Run the default baseline bundle.",
            ),
            structure_source="prepared_from_smiles",
            failure_reporting="Return partial or failed if Amesp fails.",
        ),
        smiles="N",
        label="baseline_ct_source",
        workdir=tmp_path / "baseline_ct_source_workdir",
        available_artifacts={},
        round_index=2,
    )

    ct_result = tool.execute(
        plan=MicroscopicExecutionPlan(
            local_goal="Extract bounded CT descriptors from the reusable baseline bundle.",
            requested_deliverables=[
                "CT-descriptor availability summary",
                "artifact-backed CT surrogate summary",
            ],
            capability_route="artifact_parse_only",
            microscopic_tool_request=MicroscopicToolRequest(
                capability_name="extract_ct_descriptors_from_bundle",
                perform_new_calculation=False,
                reuse_existing_artifacts_only=True,
                artifact_bundle_id="round_02_baseline_bundle",
                artifact_source_round=2,
                artifact_scope="baseline_bundle",
                state_window=[1, 2],
                descriptor_scope=["dominant_transitions", "ct_localization_proxy"],
                deliverables=[
                    "CT-descriptor availability summary",
                    "artifact-backed CT surrogate summary",
                ],
                requested_route_summary="Inspect the reusable baseline bundle for bounded CT-descriptor surrogates.",
            ),
            structure_source="existing_prepared_structure",
            failure_reporting="Return partial or failed if parsing fails.",
        ),
        smiles="N",
        label="baseline_ct_extract",
        workdir=tmp_path / "baseline_ct_extract_workdir",
        available_artifacts={**baseline_result.generated_artifacts, "source_round": 2},
        round_index=4,
    )

    assert ct_result.executed_capability == "extract_ct_descriptors_from_bundle"
    assert ct_result.route == "artifact_parse_only"
    assert ct_result.performed_new_calculations is False
    assert ct_result.reused_existing_artifacts is True
    assert ct_result.route_summary["artifact_scope"] == "baseline_bundle"
    assert ct_result.route_summary["ct_proxy_availability"] == "partial_observable_only"
    assert "ground_state_dipole" in ct_result.route_summary["available_ct_surrogates"]
    assert "dominant_transitions" in ct_result.route_summary["available_ct_surrogates"]
    assert "CT/localization proxy" in ct_result.missing_deliverables
    assert "dominant transitions" not in ct_result.missing_deliverables
    assert ct_result.parsed_snapshot_records[0]["dominant_transitions"] != "not_available"
    assert len(ct_result.parsed_snapshot_records) == 1


def test_amesp_inspect_raw_artifact_bundle_reuses_baseline_bundle_artifacts(
    tmp_path: Path,
) -> None:
    amesp_bin = tmp_path / "amesp"
    amesp_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    tool = AmespBaselineMicroscopicTool(
        amesp_bin=amesp_bin,
        structure_preparer=_fake_structure_preparer,
        subprocess_runner=_fake_subprocess_success,
    )

    baseline_result = tool.execute(
        plan=MicroscopicExecutionPlan(
            local_goal="Generate a baseline bundle for later raw inspection.",
            requested_deliverables=["S0 optimized geometry", "vertical excited-state manifold"],
            capability_route="baseline_bundle",
            microscopic_tool_request=MicroscopicToolRequest(
                capability_name="run_baseline_bundle",
                perform_new_calculation=True,
                optimize_ground_state=True,
                state_window=[1, 2],
                deliverables=["S0 optimized geometry", "vertical excited-state manifold"],
                requested_route_summary="Run the default baseline bundle.",
            ),
            structure_source="prepared_from_smiles",
            failure_reporting="Return partial or failed if Amesp fails.",
        ),
        smiles="N",
        label="baseline_raw_source",
        workdir=tmp_path / "baseline_raw_source_workdir",
        available_artifacts={},
        round_index=2,
    )

    inspect_result = tool.execute(
        plan=MicroscopicExecutionPlan(
            local_goal="Inspect the reusable baseline bundle for raw-file coverage.",
            requested_deliverables=[
                "raw artifact file inventory",
                "extractable observable inventory",
                "raw inspection notes",
            ],
            capability_route="artifact_parse_only",
            microscopic_tool_request=MicroscopicToolRequest(
                capability_name="inspect_raw_artifact_bundle",
                perform_new_calculation=False,
                reuse_existing_artifacts_only=True,
                artifact_bundle_id="round_02_baseline_bundle",
                artifact_source_round=2,
                artifact_scope="baseline_bundle",
                requested_observable_scope=["ground_state_dipole", "vertical_excitation_energies"],
                deliverables=[
                    "raw artifact file inventory",
                    "extractable observable inventory",
                    "raw inspection notes",
                ],
                requested_route_summary="Inspect the reusable baseline bundle for raw-file coverage.",
            ),
            structure_source="existing_prepared_structure",
            failure_reporting="Return partial or failed if inspection fails.",
        ),
        smiles="N",
        label="baseline_raw_inspect",
        workdir=tmp_path / "baseline_raw_inspect_workdir",
        available_artifacts={**baseline_result.generated_artifacts, "source_round": 2},
        round_index=4,
    )

    assert inspect_result.executed_capability == "inspect_raw_artifact_bundle"
    assert inspect_result.route == "artifact_parse_only"
    assert inspect_result.performed_new_calculations is False
    assert inspect_result.reused_existing_artifacts is True
    assert inspect_result.route_summary["artifact_scope"] == "baseline_bundle"
    assert "s0_aop_path" in inspect_result.route_summary["available_raw_files"]
    assert "s1_aop_path" in inspect_result.route_summary["available_raw_files"]
    assert "ground_state_dipole" in inspect_result.route_summary["extractable_observables"]
    assert "vertical_excitation_energies" in inspect_result.route_summary["extractable_observables"]
    assert "dominant_transitions" in inspect_result.route_summary["extractable_observables"]
    assert inspect_result.missing_deliverables == []


def test_amesp_extract_geometry_descriptors_from_bundle_reuses_baseline_bundle_artifacts(
    tmp_path: Path,
) -> None:
    amesp_bin = tmp_path / "amesp"
    amesp_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    tool = AmespBaselineMicroscopicTool(
        amesp_bin=amesp_bin,
        structure_preparer=_fake_geometry_structure_preparer,
        subprocess_runner=_fake_geometry_subprocess_success,
    )

    baseline_result = tool.execute(
        plan=MicroscopicExecutionPlan(
            local_goal="Generate a baseline bundle for later geometry-descriptor extraction.",
            requested_deliverables=["S0 optimized geometry", "vertical excited-state manifold"],
            capability_route="baseline_bundle",
            microscopic_tool_request=MicroscopicToolRequest(
                capability_name="run_baseline_bundle",
                perform_new_calculation=True,
                optimize_ground_state=True,
                state_window=[1, 2],
                deliverables=["S0 optimized geometry", "vertical excited-state manifold"],
                requested_route_summary="Run the default baseline bundle.",
            ),
            structure_source="prepared_from_smiles",
            failure_reporting="Return partial or failed if Amesp fails.",
        ),
        smiles="OCC=N",
        label="baseline_geometry_source",
        workdir=tmp_path / "baseline_geometry_source_workdir",
        available_artifacts={},
        round_index=2,
    )

    geometry_result = tool.execute(
        plan=MicroscopicExecutionPlan(
            local_goal="Extract bounded intramolecular geometry descriptors from the reusable baseline bundle.",
            requested_deliverables=[
                "geometry-descriptor availability summary",
                "bounded geometry descriptor records",
            ],
            capability_route="artifact_parse_only",
            microscopic_tool_request=MicroscopicToolRequest(
                capability_name="extract_geometry_descriptors_from_bundle",
                perform_new_calculation=False,
                reuse_existing_artifacts_only=True,
                artifact_bundle_id="round_02_baseline_bundle",
                artifact_source_round=2,
                artifact_scope="baseline_bundle",
                descriptor_scope=["intramolecular_hbond_candidates", "local_planarity_proxy"],
                deliverables=[
                    "geometry-descriptor availability summary",
                    "bounded geometry descriptor records",
                ],
                requested_route_summary="Inspect the reusable baseline bundle for bounded intramolecular geometry descriptors.",
            ),
            structure_source="existing_prepared_structure",
            failure_reporting="Return partial or failed if parsing fails.",
        ),
        smiles="OCC=N",
        label="baseline_geometry_extract",
        workdir=tmp_path / "baseline_geometry_extract_workdir",
        available_artifacts={**baseline_result.generated_artifacts, "source_round": 2},
        round_index=4,
    )

    assert geometry_result.executed_capability == "extract_geometry_descriptors_from_bundle"
    assert geometry_result.route == "artifact_parse_only"
    assert geometry_result.performed_new_calculations is False
    assert geometry_result.reused_existing_artifacts is True
    assert geometry_result.route_summary["artifact_scope"] == "baseline_bundle"
    assert geometry_result.route_summary["geometry_proxy_availability"] == "available"
    assert "intramolecular_hbond_candidates" in geometry_result.route_summary["available_geometry_descriptors"]
    assert len(geometry_result.parsed_snapshot_records) == 1
    record = geometry_result.parsed_snapshot_records[0]
    assert record["donor_atom_count"] == 1
    assert record["acceptor_atom_count"] >= 2
    assert record["best_intramolecular_hbond"] is not None
    assert record["has_hbond_like_candidate"] is True
    assert record["local_planarity_proxy"] is not None
    assert geometry_result.missing_deliverables == []


def test_amesp_partial_torsion_bundle_is_discoverable_for_raw_inspection(
    tmp_path: Path, monkeypatch
) -> None:
    amesp_bin = tmp_path / "amesp"
    amesp_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr("aie_mas.tools.amesp._generate_torsion_snapshot_bundle", _fake_torsion_snapshot_bundle)
    tool = AmespBaselineMicroscopicTool(
        amesp_bin=amesp_bin,
        structure_preparer=_fake_structure_preparer,
        subprocess_runner=_fake_subprocess_partial_torsion_s1,
    )

    try:
        tool.execute(
            plan=MicroscopicExecutionPlan(
                local_goal="Generate bounded torsion snapshots even if the first S1 step is unstable.",
                requested_deliverables=["torsion sensitivity summary"],
                capability_route="torsion_snapshot_follow_up",
                microscopic_tool_request=MicroscopicToolRequest(
                    capability_name="run_torsion_snapshots",
                    perform_new_calculation=True,
                    optimize_ground_state=False,
                    artifact_scope="torsion_snapshots",
                    dihedral_id="dih_0_1_2_3",
                    dihedral_atom_indices=[0, 1, 2, 3],
                    snapshot_count=2,
                    angle_offsets_deg=[0.0, 30.0],
                    state_window=[1, 2],
                    deliverables=["torsion sensitivity summary"],
                    requested_route_summary="Generate two torsion snapshots for later reuse.",
                ),
                structure_source="prepared_from_smiles",
                failure_reporting="Return partial or failed if Amesp fails.",
            ),
            smiles="N",
            label="partial_torsion_source",
            workdir=tmp_path / "partial_torsion_source_workdir",
            available_artifacts={},
            round_index=2,
        )
    except AmespExecutionError as exc:
        partial_payload = exc
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected the torsion route to fail partially.")

    assert partial_payload.status == "partial"
    registry_entries = list(partial_payload.generated_artifacts.get("artifact_bundle_registry_entries") or [])
    assert len(registry_entries) == 1
    assert registry_entries[0]["artifact_bundle"]["bundle_id"] == "round_02_torsion_snapshots"
    assert registry_entries[0]["artifact_bundle"]["bundle_completion_status"] == "partial"

    inspect_result = tool.execute(
        plan=MicroscopicExecutionPlan(
            local_goal="Inspect the partial torsion bundle for raw-file coverage.",
            requested_deliverables=[
                "raw artifact file inventory",
                "extractable observable inventory",
                "raw inspection notes",
            ],
            capability_route="artifact_parse_only",
            microscopic_tool_request=MicroscopicToolRequest(
                capability_name="inspect_raw_artifact_bundle",
                perform_new_calculation=False,
                reuse_existing_artifacts_only=True,
                artifact_bundle_id="round_02_torsion_snapshots",
                artifact_source_round=2,
                artifact_scope="torsion_snapshots",
                requested_observable_scope=["stdout_logs", "vertical_excitation_energies"],
                deliverables=[
                    "raw artifact file inventory",
                    "extractable observable inventory",
                    "raw inspection notes",
                ],
                requested_route_summary="Inspect the partial torsion bundle without new calculations.",
            ),
            structure_source="existing_prepared_structure",
            failure_reporting="Return partial or failed if inspection fails.",
        ),
        smiles="N",
        label="partial_torsion_inspect",
        workdir=tmp_path / "partial_torsion_inspect_workdir",
        available_artifacts={**partial_payload.generated_artifacts, "source_round": 2},
        round_index=4,
    )

    assert inspect_result.executed_capability == "inspect_raw_artifact_bundle"
    assert inspect_result.route_summary["artifact_scope"] == "torsion_snapshots"
    assert inspect_result.route_summary["source_bundle_completion_status"] == "partial"
    assert any(
        "partial" in note.lower()
        for note in inspect_result.route_summary["inspection_notes"]
    )
    assert inspect_result.parsed_snapshot_records[0]["source_snapshot_status"] == "partial"


def test_amesp_parse_snapshot_outputs_rejects_noncanonical_artifact_bundle_id(
    tmp_path: Path, monkeypatch
) -> None:
    amesp_bin = tmp_path / "amesp"
    amesp_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr("aie_mas.tools.amesp._generate_torsion_snapshot_bundle", _fake_torsion_snapshot_bundle)
    tool = AmespBaselineMicroscopicTool(
        amesp_bin=amesp_bin,
        structure_preparer=_fake_structure_preparer,
        subprocess_runner=_fake_subprocess_success,
    )

    torsion_result = tool.execute(
        plan=MicroscopicExecutionPlan(
            local_goal="Generate bounded torsion snapshots for later parsing.",
            requested_deliverables=["torsion sensitivity summary"],
            capability_route="torsion_snapshot_follow_up",
            microscopic_tool_request=MicroscopicToolRequest(
                capability_name="run_torsion_snapshots",
                perform_new_calculation=True,
                artifact_scope="torsion_snapshots",
                dihedral_id="dih_0_1_2_3",
                dihedral_atom_indices=[0, 1, 2, 3],
                snapshot_count=2,
                angle_offsets_deg=[25.0, -25.0],
                state_window=[1, 2],
                deliverables=["torsion sensitivity summary"],
                requested_route_summary="Generate two torsion snapshots for later reuse.",
            ),
            structure_source="prepared_from_smiles",
            failure_reporting="Return partial or failed if Amesp fails.",
        ),
        smiles="N",
        label="parse_source_noncanonical",
        workdir=tmp_path / "parse_source_noncanonical_workdir",
        available_artifacts={},
        round_index=2,
    )

    try:
        tool.execute(
            plan=MicroscopicExecutionPlan(
                local_goal="Reject noncanonical artifact bundle IDs.",
                requested_deliverables=["per-snapshot excitation records"],
                capability_route="artifact_parse_only",
                microscopic_tool_request=MicroscopicToolRequest(
                    capability_name="parse_snapshot_outputs",
                    perform_new_calculation=False,
                    reuse_existing_artifacts_only=True,
                    artifact_bundle_id="7bc31a3d4c4d_round_01_micro",
                    artifact_scope="torsion_snapshots",
                    state_window=[1, 2],
                    deliverables=["per-snapshot excitation records"],
                    requested_route_summary="Reject ad hoc artifact bundle labels.",
                ),
                structure_source="existing_prepared_structure",
                failure_reporting="Return partial or failed if parsing fails.",
            ),
            smiles="N",
            label="parse_noncanonical",
            workdir=tmp_path / "parse_noncanonical_workdir",
            available_artifacts={**torsion_result.generated_artifacts, "source_round": 2},
            round_index=4,
        )
    except AmespExecutionError as exc:
        assert exc.code == "precondition_missing"
        assert "canonical bundle id" in exc.message.lower()
    else:  # pragma: no cover
        raise AssertionError("Expected parse-only execution to reject a noncanonical artifact bundle ID.")


def test_amesp_parse_snapshot_outputs_can_select_bundle_from_registry_sources(
    tmp_path: Path, monkeypatch
) -> None:
    amesp_bin = tmp_path / "amesp"
    amesp_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr("aie_mas.tools.amesp._generate_torsion_snapshot_bundle", _fake_torsion_snapshot_bundle)
    tool = AmespBaselineMicroscopicTool(
        amesp_bin=amesp_bin,
        structure_preparer=_fake_structure_preparer,
        subprocess_runner=_fake_subprocess_success,
    )

    round_2_result = tool.execute(
        plan=MicroscopicExecutionPlan(
            local_goal="Generate round 2 torsion snapshots.",
            requested_deliverables=["torsion sensitivity summary"],
            capability_route="torsion_snapshot_follow_up",
            microscopic_tool_request=MicroscopicToolRequest(
                capability_name="run_torsion_snapshots",
                perform_new_calculation=True,
                artifact_scope="torsion_snapshots",
                dihedral_id="dih_0_1_2_3",
                dihedral_atom_indices=[0, 1, 2, 3],
                snapshot_count=2,
                angle_offsets_deg=[25.0, -25.0],
                state_window=[1, 2],
                deliverables=["torsion sensitivity summary"],
                requested_route_summary="Generate round 2 torsion snapshots.",
            ),
            structure_source="prepared_from_smiles",
            failure_reporting="Return partial or failed if Amesp fails.",
        ),
        smiles="N",
        label="registry_round_02",
        workdir=tmp_path / "registry_round_02_workdir",
        available_artifacts={},
        round_index=2,
    )
    round_4_result = tool.execute(
        plan=MicroscopicExecutionPlan(
            local_goal="Generate round 4 torsion snapshots.",
            requested_deliverables=["torsion sensitivity summary"],
            capability_route="torsion_snapshot_follow_up",
            microscopic_tool_request=MicroscopicToolRequest(
                capability_name="run_torsion_snapshots",
                perform_new_calculation=True,
                artifact_scope="torsion_snapshots",
                dihedral_id="dih_0_1_2_3",
                dihedral_atom_indices=[0, 1, 2, 3],
                snapshot_count=2,
                angle_offsets_deg=[35.0, 70.0],
                state_window=[1, 2],
                deliverables=["torsion sensitivity summary"],
                requested_route_summary="Generate round 4 torsion snapshots.",
            ),
            structure_source="prepared_from_smiles",
            failure_reporting="Return partial or failed if Amesp fails.",
        ),
        smiles="N",
        label="registry_round_04",
        workdir=tmp_path / "registry_round_04_workdir",
        available_artifacts={},
        round_index=4,
    )

    parsed_result = tool.execute(
        plan=MicroscopicExecutionPlan(
            local_goal="Select round 2 torsion artifacts through discovery before parse-only reuse.",
            requested_deliverables=["per-snapshot excitation records"],
            capability_route="artifact_parse_only",
            microscopic_tool_plan=MicroscopicToolPlan(
                calls=[
                    MicroscopicToolCall(
                        call_id="discover_artifact_bundles",
                        call_kind="discovery",
                        request=MicroscopicToolRequest(
                            capability_name="list_artifact_bundles",
                            artifact_kind="torsion_snapshots",
                            perform_new_calculation=False,
                            reuse_existing_artifacts_only=True,
                            requested_route_summary="List reusable torsion bundles.",
                        ),
                    ),
                    MicroscopicToolCall(
                        call_id="execute_parse",
                        call_kind="execution",
                        request=MicroscopicToolRequest(
                            capability_name="parse_snapshot_outputs",
                            perform_new_calculation=False,
                            reuse_existing_artifacts_only=True,
                            state_window=[1, 2],
                            deliverables=["per-snapshot excitation records"],
                            requested_route_summary="Parse the selected torsion bundle without new calculations.",
                        ),
                    ),
                ],
                selection_policy=SelectionPolicy(
                    artifact_kind="torsion_snapshots",
                    source_round_preference=2,
                ),
            ),
            structure_source="existing_prepared_structure",
            failure_reporting="Return partial or failed if parsing fails.",
        ),
        smiles="N",
        label="registry_parse",
        workdir=tmp_path / "registry_parse_workdir",
        available_artifacts={
            **round_4_result.generated_artifacts,
            "source_round": 4,
            "artifact_bundle_registry_sources": [
                {"source_round": 2, "generated_artifacts": {**round_2_result.generated_artifacts, "source_round": 2}},
                {"source_round": 4, "generated_artifacts": {**round_4_result.generated_artifacts, "source_round": 4}},
            ],
        },
        round_index=5,
    )

    assert parsed_result.executed_capability == "parse_snapshot_outputs"
    assert parsed_result.resolved_target_ids["artifact_bundle_id"] == "round_02_torsion_snapshots"
    assert parsed_result.route_summary["artifact_source_round"] == 2
    assert parsed_result.performed_new_calculations is False


def test_amesp_tool_uses_discovery_before_torsion_execution_when_dihedral_id_is_missing(
    tmp_path: Path, monkeypatch
) -> None:
    amesp_bin = tmp_path / "amesp"
    amesp_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr("aie_mas.tools.amesp._generate_torsion_snapshot_bundle", _fake_torsion_snapshot_bundle)
    monkeypatch.setattr(
        "aie_mas.tools.amesp._list_rotatable_dihedral_descriptors",
        lambda prepared: [
            DihedralDescriptor(
                dihedral_id="dih_9_10_11_12",
                atom_indices=[9, 10, 11, 12],
                central_bond_indices=[10, 11],
                label="peripheral aryl-aryl",
                bond_type="aryl-aryl",
                adjacent_to_nsnc_core=False,
                central_conjugation_relevance="medium",
                peripheral=True,
                rotatable=True,
            ),
            DihedralDescriptor(
                dihedral_id="dih_0_1_2_3",
                atom_indices=[0, 1, 2, 3],
                central_bond_indices=[1, 2],
                label="core-adjacent heteroaryl linkage",
                bond_type="heteroaryl-linkage",
                adjacent_to_nsnc_core=True,
                central_conjugation_relevance="high",
                peripheral=False,
                rotatable=True,
            ),
        ],
    )
    tool = AmespBaselineMicroscopicTool(
        amesp_bin=amesp_bin,
        structure_preparer=_fake_structure_preparer,
        subprocess_runner=_fake_subprocess_success,
    )

    result = tool.execute(
        plan=MicroscopicExecutionPlan(
            local_goal="Discover a core-adjacent dihedral and execute two torsion snapshots.",
            requested_deliverables=["torsion sensitivity summary"],
            capability_route="torsion_snapshot_follow_up",
            microscopic_tool_plan=MicroscopicToolPlan(
                calls=[
                    MicroscopicToolCall(
                        call_id="discover_dihedrals",
                        call_kind="discovery",
                        request=MicroscopicToolRequest(
                            capability_name="list_rotatable_dihedrals",
                            structure_source="round_s0_optimized_geometry",
                            min_relevance="high",
                            include_peripheral=False,
                            requested_route_summary="Discover usable dihedral IDs.",
                        ),
                    ),
                    MicroscopicToolCall(
                        call_id="execute_torsion",
                        call_kind="execution",
                        request=MicroscopicToolRequest(
                            capability_name="run_torsion_snapshots",
                            perform_new_calculation=True,
                            snapshot_count=2,
                            angle_offsets_deg=[35.0, 70.0],
                            state_window=[1, 2],
                            deliverables=["torsion sensitivity summary"],
                            requested_route_summary="Use the discovered core-adjacent dihedral for exact torsion snapshots.",
                        ),
                    ),
                ],
                selection_policy=SelectionPolicy(
                    prefer_adjacent_to_nsnc_core=True,
                    min_relevance="high",
                    include_peripheral=False,
                    preferred_bond_types=["heteroaryl-linkage"],
                ),
            ),
            structure_source="prepared_from_smiles",
            failure_reporting="Return partial or failed if Amesp fails.",
        ),
        smiles="N",
        label="two_stage_case",
        workdir=tmp_path / "two_stage_workdir",
        available_artifacts={},
    )

    assert result.executed_capability == "run_torsion_snapshots"
    assert result.resolved_target_ids["dihedral_id"] == "dih_0_1_2_3"
    assert any("NSNC-like core" in note or "NSNC-like" in note for note in result.honored_constraints)
    assert result.route_summary["requested_selection_policy"]["min_relevance"] == "high"
    assert result.route_summary["selected_dihedral_id"] == "dih_0_1_2_3"
    assert result.route_summary["candidate_count_initial"] == 2
    assert result.route_summary["selection_relaxations_applied"] == []
    assert all(record["dihedral_atoms"] == [0, 1, 2, 3] for record in result.route_records)


def test_amesp_torsion_selection_relaxes_soft_preferences_before_execution(
    tmp_path: Path, monkeypatch
) -> None:
    amesp_bin = tmp_path / "amesp"
    amesp_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr("aie_mas.tools.amesp._generate_torsion_snapshot_bundle", _fake_torsion_snapshot_bundle)
    monkeypatch.setattr(
        "aie_mas.tools.amesp._list_rotatable_dihedral_descriptors",
        lambda prepared: [
            DihedralDescriptor(
                dihedral_id="dih_9_10_11_12",
                atom_indices=[9, 10, 11, 12],
                central_bond_indices=[10, 11],
                label="peripheral medium rotor",
                bond_type="aryl-aryl",
                adjacent_to_nsnc_core=False,
                central_conjugation_relevance="medium",
                peripheral=True,
                rotatable=True,
            ),
        ],
    )
    tool = AmespBaselineMicroscopicTool(
        amesp_bin=amesp_bin,
        structure_preparer=_fake_structure_preparer,
        subprocess_runner=_fake_subprocess_success,
    )

    result = tool.execute(
        plan=MicroscopicExecutionPlan(
            local_goal="Try a donor-aryl preference first, but allow bounded fallback if unavailable.",
            requested_deliverables=["torsion sensitivity summary"],
            capability_route="torsion_snapshot_follow_up",
            microscopic_tool_plan=MicroscopicToolPlan(
                calls=[
                    MicroscopicToolCall(
                        call_id="discover_dihedrals",
                        call_kind="discovery",
                        request=MicroscopicToolRequest(
                            capability_name="list_rotatable_dihedrals",
                            structure_source="round_s0_optimized_geometry",
                            min_relevance="high",
                            include_peripheral=False,
                            requested_route_summary="Discover usable dihedral IDs.",
                        ),
                    ),
                    MicroscopicToolCall(
                        call_id="execute_torsion",
                        call_kind="execution",
                        request=MicroscopicToolRequest(
                            capability_name="run_torsion_snapshots",
                            perform_new_calculation=True,
                            snapshot_count=2,
                            angle_offsets_deg=[35.0, 70.0],
                            state_window=[1, 2],
                            deliverables=["torsion sensitivity summary"],
                            requested_route_summary="Use the best available torsion if the preferred one is unavailable.",
                        ),
                    ),
                ],
                selection_policy=SelectionPolicy(
                    exclude_dihedral_ids=["dih_9_10_11_12"],
                    prefer_adjacent_to_nsnc_core=True,
                    min_relevance="high",
                    include_peripheral=False,
                    preferred_bond_types=["heteroaryl-linkage"],
                    selection_relaxation_allowed=True,
                ),
            ),
            structure_source="prepared_from_smiles",
            failure_reporting="Return partial or failed if Amesp fails.",
        ),
        smiles="N",
        label="relaxed_torsion_case",
        workdir=tmp_path / "relaxed_torsion_workdir",
        available_artifacts={},
    )

    assert result.executed_capability == "run_torsion_snapshots"
    assert result.resolved_target_ids["dihedral_id"] == "dih_9_10_11_12"
    assert result.route_summary["selected_dihedral_id"] == "dih_9_10_11_12"
    assert result.route_summary["candidate_count_initial"] == 1
    assert result.route_summary["candidate_count_after_hard_constraints"] == 1
    assert result.route_summary["candidate_count_after_relaxation"] == 1
    assert result.route_summary["selection_relaxations_applied"] == [
        "min_relevance: high -> medium",
        "include_peripheral: false -> true",
        "preferred_bond_types: broadened to all known torsion bond types",
        "exclude_dihedral_ids: softened to avoid-only when alternatives exist",
    ]
    assert "highest-ranked hard-eligible torsion candidate" in result.route_summary["selection_rationale"]


def test_amesp_torsion_hard_exclusions_still_fail_when_they_exhaust_candidates(
    tmp_path: Path, monkeypatch
) -> None:
    amesp_bin = tmp_path / "amesp"
    amesp_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(
        "aie_mas.tools.amesp._list_rotatable_dihedral_descriptors",
        lambda prepared: [
            DihedralDescriptor(
                dihedral_id="dih_9_10_11_12",
                atom_indices=[9, 10, 11, 12],
                central_bond_indices=[10, 11],
                label="only rotor",
                bond_type="aryl-aryl",
                adjacent_to_nsnc_core=False,
                central_conjugation_relevance="medium",
                peripheral=True,
                rotatable=True,
            ),
        ],
    )
    tool = AmespBaselineMicroscopicTool(
        amesp_bin=amesp_bin,
        structure_preparer=_fake_structure_preparer,
        subprocess_runner=_fake_subprocess_success,
    )

    try:
        tool.execute(
            plan=MicroscopicExecutionPlan(
                local_goal="Require a torsion that is also hard-excluded.",
                requested_deliverables=["torsion sensitivity summary"],
                capability_route="torsion_snapshot_follow_up",
                microscopic_tool_plan=MicroscopicToolPlan(
                    calls=[
                        MicroscopicToolCall(
                            call_id="discover_dihedrals",
                            call_kind="discovery",
                            request=MicroscopicToolRequest(
                                capability_name="list_rotatable_dihedrals",
                                structure_source="round_s0_optimized_geometry",
                                requested_route_summary="Discover usable dihedral IDs.",
                            ),
                        ),
                        MicroscopicToolCall(
                            call_id="execute_torsion",
                            call_kind="execution",
                            request=MicroscopicToolRequest(
                                capability_name="run_torsion_snapshots",
                                perform_new_calculation=True,
                                snapshot_count=2,
                                angle_offsets_deg=[35.0, 70.0],
                                state_window=[1, 2],
                                deliverables=["torsion sensitivity summary"],
                                requested_route_summary="Use a discoverable torsion if possible.",
                            ),
                        ),
                    ],
                    selection_policy=SelectionPolicy(
                        hard_exclude_dihedral_ids=["dih_9_10_11_12"],
                        selection_relaxation_allowed=True,
                    ),
                ),
                structure_source="prepared_from_smiles",
                failure_reporting="Return partial or failed if Amesp fails.",
            ),
            smiles="N",
            label="hard_excluded_torsion_case",
            workdir=tmp_path / "hard_excluded_torsion_workdir",
            available_artifacts={},
        )
    except AmespExecutionError as exc:
        assert exc.code == "precondition_missing"
        assert exc.structured_results["selection_failure_reason"] == "hard_exclusions_exhausted"
        assert exc.structured_results["candidate_count_initial"] == 1
        assert exc.structured_results["candidate_count_after_hard_constraints"] == 0
    else:  # pragma: no cover
        raise AssertionError("Expected hard-excluded torsion discovery to fail.")


def test_amesp_parse_snapshot_outputs_fails_when_artifacts_are_missing(tmp_path: Path) -> None:
    amesp_bin = tmp_path / "amesp"
    amesp_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    tool = AmespBaselineMicroscopicTool(
        amesp_bin=amesp_bin,
        structure_preparer=_fake_structure_preparer,
        subprocess_runner=_fake_subprocess_success,
    )

    try:
        tool.execute(
            plan=MicroscopicExecutionPlan(
                local_goal="Parse nonexistent artifacts.",
                requested_deliverables=["per-snapshot excitation records"],
                capability_route="artifact_parse_only",
                microscopic_tool_request=MicroscopicToolRequest(
                    capability_name="parse_snapshot_outputs",
                    perform_new_calculation=False,
                    reuse_existing_artifacts_only=True,
                    artifact_source_round=2,
                    artifact_scope="torsion_snapshots",
                    deliverables=["per-snapshot excitation records"],
                    requested_route_summary="Attempt parse-only reuse.",
                ),
                structure_source="existing_prepared_structure",
                failure_reporting="Return partial or failed if parsing fails.",
            ),
            smiles="N",
            label="missing_parse",
            workdir=tmp_path / "missing_parse_workdir",
            available_artifacts={"source_round": 2},
            round_index=4,
        )
    except AmespExecutionError as exc:
        assert exc.code == "precondition_missing"
    else:  # pragma: no cover
        raise AssertionError("Expected parse-only execution to fail when no snapshot artifacts are available.")


class _SuccessfulAmespTool:
    name = "amesp_baseline_microscopic"

    def execute(
        self,
        *,
        plan,
        smiles,
        label,
        workdir,
        available_artifacts,
        progress_callback=None,
        round_index=1,
        case_id=None,
        current_hypothesis=None,
    ):
        del smiles, label, workdir, available_artifacts, progress_callback, round_index, case_id, current_hypothesis
        tool_request = plan.microscopic_tool_request
        return AmespBaselineRunResult(
            route=getattr(plan, "capability_route", "baseline_bundle"),
            executed_capability=tool_request.capability_name,
            performed_new_calculations=tool_request.perform_new_calculation,
            reused_existing_artifacts=tool_request.reuse_existing_artifacts_only,
            structure=PreparedStructure(
                input_smiles="C1=CCCCC1",
                canonical_smiles="C1=CCCCC1",
                charge=0,
                multiplicity=1,
                heavy_atom_count=6,
                atom_count=16,
                conformer_count=10,
                selected_conformer_id=2,
                force_field="MMFF94",
                xyz_path=Path("/tmp/prepared_structure.xyz"),
                sdf_path=Path("/tmp/prepared_structure.sdf"),
                summary_path=Path("/tmp/structure_prep_summary.json"),
            ),
            s0=AmespGroundStateResult(
                final_energy_hartree=-231.123,
                dipole_debye=(0.0, 0.1, 0.0, 0.1),
                mulliken_charges=[-0.1, 0.1],
                homo_lumo_gap_ev=7.21,
                geometry_atom_count=16,
                geometry_xyz_path="/tmp/s0.xyz",
                rmsd_from_prepared_structure_angstrom=0.051,
            ),
            s1=AmespExcitedStateResult(
                excited_states=[
                    AmespExcitedState(
                        state_index=1,
                        total_energy_hartree=-231.0,
                        oscillator_strength=0.245,
                        spin_square=0.0,
                        excitation_energy_ev=3.347,
                    ),
                    AmespExcitedState(
                        state_index=2,
                        total_energy_hartree=-230.95,
                        oscillator_strength=0.02,
                        spin_square=0.0,
                        excitation_energy_ev=3.521,
                    )
                ],
                first_excitation_energy_ev=3.347,
                first_oscillator_strength=0.245,
                state_count=2,
            ),
            route_records=[],
            route_summary={"state_count": 2},
            raw_step_results={"s0_optimization": {"exit_code": 0}, "s1_vertical_excitation": {"exit_code": 0}},
            generated_artifacts={"prepared_xyz_path": "/tmp/prepared_structure.xyz", "s0_aop_path": "/tmp/s0.aop"},
        )


def test_real_microscopic_agent_builds_understanding_and_execution_plan(
    tmp_path: Path,
    install_specialized_test_doubles,
) -> None:
    install_specialized_test_doubles()
    progress_events: list[dict[str, object]] = []
    agent = MicroscopicAgent(
        amesp_tool=_SuccessfulAmespTool(),
        tools_work_dir=tmp_path / "tools",
        progress_callback=progress_events.append,
    )
    task_spec = MicroscopicTaskSpec(
        mode="baseline_s0_s1",
        task_label="initial-baseline",
        objective="Use Amesp to optimize the ground-state geometry and characterize the first excited singlet.",
    )

    report = agent.run(
        smiles="C1=CCCCC1",
        task_received=(
            "Use Amesp to optimize the ground-state geometry, summarize Mulliken charges and dipole, "
            "and characterize the first excited singlet oscillator strength."
        ),
        task_spec=task_spec,
        current_hypothesis="restriction of intramolecular motion (RIM)-dominated AIE",
        recent_rounds_context=[{"round_id": 1, "action_taken": "macro, microscopic", "main_gap": "Need micro evidence."}],
        case_id="case123",
        round_index=1,
    )

    assert report.task_understanding
    assert report.reasoning_summary
    assert report.execution_plan
    assert report.result_summary
    assert report.remaining_local_uncertainty
    assert report.generated_artifacts["prepared_xyz_path"] == "/tmp/prepared_structure.xyz"
    assert report.structured_results["execution_plan"]["plan_version"] == "amesp_baseline_v1"
    assert report.structured_results["execution_plan"]["steps"][1]["step_type"] == "s0_optimization"
    assert report.structured_results["s1"]["first_oscillator_strength"] == 0.245
    assert report.structured_results["execution_plan"]["capability_route"] == "baseline_bundle"
    assert report.structured_results["vertical_state_manifold"]["state_count"] == 2
    assert report.task_completion_status == "completed"
    assert "The Planner requested `run_baseline_bundle`." in report.task_completion
    assert "All requested deliverables were produced" in report.task_completion
    assert "bounded amesp route" in report.execution_plan.lower()
    assert any(
        event["phase"] == "probe"
        and event["details"].get("probe_stage") == "reasoning"
        and event["details"].get("probe_status") == "start"
        for event in progress_events
    )
    assert any(
        event["phase"] == "probe"
        and event["details"].get("probe_stage") == "execution_plan"
        and event["details"].get("probe_status") == "end"
        for event in progress_events
    )


class _FailingAmespTool:
    name = "amesp_baseline_microscopic"

    def execute(
        self,
        *,
        plan,
        smiles,
        label,
        workdir,
        available_artifacts,
        progress_callback=None,
        round_index=1,
        case_id=None,
        current_hypothesis=None,
    ):
        del smiles, label, workdir, available_artifacts, progress_callback, round_index, case_id, current_hypothesis
        raise AmespExecutionError(
            "subprocess_failed",
            "The S1 TDDFT step failed after the S0 optimization completed.",
            generated_artifacts={"s0_aop_path": "/tmp/s0.aop"},
            structured_results={
                "s0": {"final_energy_hartree": -55.79},
                "executed_capability": plan.microscopic_tool_request.capability_name,
                "performed_new_calculations": True,
                "reused_existing_artifacts": False,
            },
            status="partial",
        )


class _UnsupportedRouteAmespTool:
    name = "amesp_baseline_microscopic"

    def execute(
        self,
        *,
        plan,
        smiles,
        label,
        workdir,
        available_artifacts,
        progress_callback=None,
        round_index=1,
        case_id=None,
        current_hypothesis=None,
    ):
        del smiles, label, workdir, available_artifacts, progress_callback, round_index, case_id, current_hypothesis
        raise AmespExecutionError(
            "capability_unsupported",
            f"Route {plan.capability_route} is not yet validated.",
            status="failed",
            structured_results={
                "executed_capability": "unsupported_excited_state_relaxation",
                "performed_new_calculations": False,
                "reused_existing_artifacts": False,
            },
        )


def test_real_microscopic_agent_returns_partial_report_on_runner_failure(
    tmp_path: Path,
    install_specialized_test_doubles,
) -> None:
    install_specialized_test_doubles()
    agent = MicroscopicAgent(
        amesp_tool=_FailingAmespTool(),
        tools_work_dir=tmp_path / "tools",
    )
    report = agent.run(
        smiles="C1=CCCCC1",
        task_received="Use Amesp to optimize S0, characterize S1, and if possible do a torsion scan.",
        current_hypothesis="restriction of intramolecular motion (RIM)-dominated AIE",
        case_id="case123",
        round_index=2,
        task_spec=MicroscopicTaskSpec(
            mode="targeted_follow_up",
            task_label="round-2-targeted",
            objective="Investigate the unresolved microscopic gap with a targeted local follow-up.",
            target_property="weak_conflict_resolution",
        ),
    )

    assert report.status == "partial"
    assert report.task_completion_status == "partial"
    assert report.reasoning_summary
    assert report.generated_artifacts["s0_aop_path"] == "/tmp/s0.aop"
    assert report.structured_results["error"]["code"] == "subprocess_failed"
    assert report.structured_results["task_completion_status"] == "partial"
    assert report.structured_results["completion_reason_code"] == "runtime_failed"
    assert "was incomplete" in report.task_completion
    assert report.structured_results["execution_plan"]["capability_route"] == "torsion_snapshot_follow_up"
    assert "torsion scan" in " ".join(report.structured_results["execution_plan"]["unsupported_requests"]).lower()
    assert "partial" in report.result_summary.lower()


def test_real_microscopic_agent_uses_conformer_follow_up_route(
    tmp_path: Path,
    install_specialized_test_doubles,
) -> None:
    install_specialized_test_doubles()
    agent = MicroscopicAgent(
        amesp_tool=_SuccessfulAmespTool(),
        tools_work_dir=tmp_path / "tools",
    )

    report = agent.run(
        smiles="C1=CCCCC1",
        task_received="Assess bounded conformer sensitivity for the unresolved microscopic follow-up.",
        current_hypothesis="restriction of intramolecular motion (RIM)-dominated AIE",
        case_id="case123",
        round_index=2,
        task_spec=MicroscopicTaskSpec(
            mode="targeted_follow_up",
            task_label="round-2-conformer",
            objective="Investigate conformer sensitivity with a bounded microscopic follow-up.",
            target_property="conformer_sensitivity",
        ),
    )

    assert report.status == "success"
    assert report.task_completion_status == "completed"
    assert report.completion_reason_code is None
    assert report.structured_results["execution_plan"]["capability_route"] == "conformer_bundle_follow_up"
    assert report.structured_results["attempted_route"] == "conformer_bundle_follow_up"


def test_real_microscopic_agent_uses_torsion_snapshot_route(
    tmp_path: Path,
    install_specialized_test_doubles,
) -> None:
    install_specialized_test_doubles()
    agent = MicroscopicAgent(
        amesp_tool=_SuccessfulAmespTool(),
        tools_work_dir=tmp_path / "tools",
    )

    report = agent.run(
        smiles="C1=CCCCC1",
        task_received="Assess bounded dihedral and torsion sensitivity for the unresolved microscopic follow-up.",
        current_hypothesis="restriction of intramolecular motion (RIM)-dominated AIE",
        case_id="case123",
        round_index=2,
        task_spec=MicroscopicTaskSpec(
            mode="targeted_follow_up",
            task_label="round-2-torsion",
            objective="Investigate torsion sensitivity with a bounded microscopic follow-up.",
            target_property="torsion_sensitivity",
        ),
    )

    assert report.status == "success"
    assert report.task_completion_status == "completed"
    assert report.structured_results["execution_plan"]["capability_route"] == "torsion_snapshot_follow_up"
    assert report.structured_results["attempted_route"] == "torsion_snapshot_follow_up"


def test_real_microscopic_agent_parses_no_reoptimization_into_tool_request(
    tmp_path: Path,
    install_specialized_test_doubles,
) -> None:
    install_specialized_test_doubles()
    agent = MicroscopicAgent(
        amesp_tool=_SuccessfulAmespTool(),
        tools_work_dir=tmp_path / "tools",
    )

    report = agent.run(
        smiles="C1=CCCCC1",
        task_received=(
            "Assess bounded dihedral sensitivity using exactly two snapshots at +/-30 degrees, "
            "and do not re-optimize the perturbed geometries before running the vertical excited-state calculation."
        ),
        current_hypothesis="ICT",
        case_id="case123",
        round_index=2,
        task_spec=MicroscopicTaskSpec(
            mode="targeted_follow_up",
            task_label="round-2-torsion-no-reopt",
            objective="Investigate torsion sensitivity without geometry re-optimization.",
            target_property="torsion_sensitivity",
        ),
    )

    request = report.structured_results["execution_plan"]["microscopic_tool_request"]
    assert request["capability_name"] == "run_torsion_snapshots"
    assert request["optimize_ground_state"] is False


def test_real_microscopic_agent_does_not_false_positive_transition_state_from_state_words(
    tmp_path: Path,
    install_specialized_test_doubles,
) -> None:
    install_specialized_test_doubles()
    agent = MicroscopicAgent(
        amesp_tool=_SuccessfulAmespTool(),
        tools_work_dir=tmp_path / "tools",
    )

    report = agent.run(
        smiles="C1=CCCCC1",
        task_received=(
            "Use Amesp to summarize the first bright state, keep the requested state_window fixed, "
            "and report the low-lying states without any new follow-up scan."
        ),
        current_hypothesis="restriction of intramolecular motion (RIM)-dominated AIE",
        case_id="case123",
        round_index=2,
        task_spec=MicroscopicTaskSpec(
            mode="baseline_s0_s1",
            task_label="round-2-state-words",
            objective="Summarize the low-lying bright-state pattern.",
        ),
    )

    assert report.task_completion_status == "completed"
    assert "transition-state optimization" not in report.structured_results["unsupported_requests"]


def test_real_microscopic_agent_reports_capability_unsupported_for_excited_state_relaxation(
    tmp_path: Path,
    install_specialized_test_doubles,
) -> None:
    install_specialized_test_doubles()
    agent = MicroscopicAgent(
        amesp_tool=_UnsupportedRouteAmespTool(),
        tools_work_dir=tmp_path / "tools",
    )

    report = agent.run(
        smiles="C1=CCCCC1",
        task_received="Attempt a low-cost excited-state geometry relaxation follow-up for S1.",
        current_hypothesis="restriction of intramolecular motion (RIM)-dominated AIE",
        case_id="case123",
        round_index=2,
        task_spec=MicroscopicTaskSpec(
            mode="targeted_follow_up",
            task_label="round-2-s1-relax",
            objective="Investigate excited-state relaxation with a bounded microscopic follow-up.",
            target_property="excited_state_relaxation",
        ),
    )

    assert report.status == "failed"
    assert report.task_completion_status == "failed"
    assert report.completion_reason_code == "capability_unsupported"
    assert report.structured_results["completion_reason_code"] == "capability_unsupported"
    assert report.structured_results["execution_plan"]["capability_route"] == "excited_state_relaxation_follow_up"
    assert "not yet validated" in report.result_summary.lower()


def test_real_tool_backend_failure_does_not_break_workflow(
    tmp_path: Path,
    install_specialized_test_doubles,
) -> None:
    install_specialized_test_doubles(
        shared_structure_tool=SharedStructurePrepTool(structure_preparer=_fake_structure_preparer),
        amesp_tool=_FailingAmespTool(),
    )

    state = run_case_workflow(
        smiles="C1=CCCCC1",
        user_query="Assess the likely AIE mechanism for this molecule.",
        execution_profile="local-dev",
        tool_backend="real",
        data_dir=tmp_path / "data",
        memory_dir=tmp_path / "memory",
        log_dir=tmp_path / "log",
        runtime_dir=tmp_path / "runtime",
    )

    assert state.microscopic_reports
    assert state.microscopic_reports[0].status == "failed" or state.microscopic_reports[0].status == "partial"
    assert state.final_answer is not None
    assert state.state_snapshot is not None
