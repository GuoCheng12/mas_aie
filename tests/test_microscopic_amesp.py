from __future__ import annotations

import json
import subprocess
from pathlib import Path

from aie_mas.agents.result_agents import MicroscopicAgent
from aie_mas.chem.structure_prep import PreparedStructure
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
E(TD) =   -55.650000000      <S**2>= 0.000     f=  0.1234
State    2 : E =    4.6637 eV     265.850 nm      37615.42 cm-1
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


def _fake_subprocess_success(cmd, cwd, env, capture_output, text):
    del env, capture_output, text
    workdir = Path(cwd)
    aip_name = Path(cmd[1]).name
    aop_name = Path(cmd[2]).name
    label = Path(aip_name).stem
    if label.endswith("_s0"):
        aop_text = S0_AOP_TEXT
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
        if label.endswith("_s0"):
            aop_text = S0_AOP_TEXT
        else:
            aop_text = S1_AOP_TEXT
        (workdir / aop_name).write_text(aop_text, encoding="utf-8")
        (workdir / f"{label}.mo").write_text("fake mo\n", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="ok\n", stderr="")

    return _runner


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
    assert "! atb opt force" in s0_input
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
    assert len(parsed_result.parsed_snapshot_records) == 1
    assert parsed_result.route_summary["artifact_scope"] == "baseline_bundle"
    assert parsed_result.generated_artifacts["artifact_bundle_id"] == "round_02_baseline_bundle"
    assert "CT/localization proxy" in parsed_result.missing_deliverables


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
    assert all(record["dihedral_atoms"] == [0, 1, 2, 3] for record in result.route_records)


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
