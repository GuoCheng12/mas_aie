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
from aie_mas.tools.amesp import (
    AmespBaselineMicroscopicTool,
    AmespExecutionError,
    AmespExcitedState,
    AmespExcitedStateResult,
    AmespGroundStateResult,
    AmespBaselineRunResult,
)
from aie_mas.tools.factory import ToolSet
from aie_mas.tools.macro import MockMacroStructureTool
from aie_mas.tools.microscopic import (
    MockS0OptimizationTool,
    MockS1OptimizationTool,
    MockTargetedMicroscopicTool,
)
from aie_mas.tools.verifier import MockVerifierEvidenceTool


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
E(TD) =   -55.650000000      <S**2>= 0.000     f=  0.1234
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
    assert result.s1.first_oscillator_strength == 0.1234
    assert result.s1.state_count == 2
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
        del plan, smiles, label, workdir, available_artifacts, progress_callback, round_index, case_id, current_hypothesis
        return AmespBaselineRunResult(
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
                    )
                ],
                first_excitation_energy_ev=3.347,
                first_oscillator_strength=0.245,
                state_count=1,
            ),
            raw_step_results={"s0_optimization": {"exit_code": 0}, "s1_vertical_excitation": {"exit_code": 0}},
            generated_artifacts={"prepared_xyz_path": "/tmp/prepared_structure.xyz", "s0_aop_path": "/tmp/s0.aop"},
        )


def test_real_microscopic_agent_builds_understanding_and_execution_plan(tmp_path: Path) -> None:
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
    assert "Amesp baseline workflow" in report.task_understanding
    assert "s1 vertical excitation" in report.execution_plan.lower()
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
        del plan, smiles, label, workdir, available_artifacts, progress_callback, round_index, case_id, current_hypothesis
        raise AmespExecutionError(
            "subprocess_failed",
            "The S1 TDDFT step failed after the S0 optimization completed.",
            generated_artifacts={"s0_aop_path": "/tmp/s0.aop"},
            structured_results={"s0": {"final_energy_hartree": -55.79}},
            status="partial",
        )


def test_real_microscopic_agent_returns_partial_report_on_runner_failure(tmp_path: Path) -> None:
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
    assert report.reasoning_summary
    assert report.generated_artifacts["s0_aop_path"] == "/tmp/s0.aop"
    assert report.structured_results["error"]["code"] == "subprocess_failed"
    assert "torsion scan" in " ".join(report.structured_results["execution_plan"]["unsupported_requests"]).lower()
    assert "partial" in report.result_summary.lower()


def test_real_tool_backend_failure_does_not_break_workflow(tmp_path: Path, monkeypatch) -> None:
    def fake_build_toolset(config):
        del config
        return ToolSet(
            macro_tool=MockMacroStructureTool(),
            s0_tool=MockS0OptimizationTool(),
            s1_tool=MockS1OptimizationTool(),
            targeted_micro_tool=MockTargetedMicroscopicTool(),
            verifier_tool=MockVerifierEvidenceTool(),
            amesp_micro_tool=_FailingAmespTool(),
        )

    monkeypatch.setattr(graph_builder, "build_toolset", fake_build_toolset)

    state = run_case_workflow(
        smiles="C1=CCCCC1",
        user_query="Assess the likely AIE mechanism for this molecule.",
        execution_profile="local-dev",
        tool_backend="real",
        planner_backend="mock",
        data_dir=tmp_path / "data",
        memory_dir=tmp_path / "memory",
        log_dir=tmp_path / "log",
        runtime_dir=tmp_path / "runtime",
    )

    assert state.microscopic_reports
    assert state.microscopic_reports[0].status == "failed" or state.microscopic_reports[0].status == "partial"
    assert state.final_answer is not None
    assert state.state_snapshot is not None
