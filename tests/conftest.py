from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import pytest

from aie_mas.agents.macro import MacroReasoningPlanDraft, MacroReasoningResponse
from aie_mas.agents.microscopic import MicroscopicReasoningPlanDraft, MicroscopicReasoningResponse
from aie_mas.chem.structure_prep import PreparedStructure
from aie_mas.graph import builder as graph_builder
from aie_mas.graph.state import SharedStructureContext
from aie_mas.tools.amesp import (
    AmespBaselineRunResult,
    AmespExcitedState,
    AmespExcitedStateResult,
    AmespGroundStateResult,
)
from aie_mas.tools.factory import ToolSet
from aie_mas.tools.macro import DeterministicMacroStructureTool
from aie_mas.tools.verifier import MockVerifierEvidenceTool
from aie_mas.utils.smiles import extract_smiles_features


class TestMacroReasoningBackend:
    def reason(self, rendered_prompt: Any, payload: dict[str, Any]) -> MacroReasoningResponse:
        del rendered_prompt
        task_instruction = str(payload["task_instruction"])
        shared_context = payload.get("shared_structure_context")
        focus_areas = _macro_focus_areas(task_instruction)
        if shared_context:
            structure_note = "A prepared shared 3D structure context is available and should be reused."
        else:
            structure_note = "Shared 3D structure context is unavailable, so SMILES-only fallback is required."
        return MacroReasoningResponse(
            task_understanding=(
                f"Use the Planner instruction to collect local macro structural evidence for the current working hypothesis "
                f"'{payload['current_hypothesis']}' without making any global mechanism judgment: {task_instruction}"
            ),
            reasoning_summary=(
                f"Interpret the Planner instruction as a bounded macro structural evidence task. {structure_note} "
                "Only deterministic low-cost topology and geometry proxies are in scope."
            ),
            execution_plan=MacroReasoningPlanDraft(
                local_goal="Collect local macro structural evidence and return only planner-readable structural results.",
                requested_deliverables=[
                    "rotor topology summary",
                    "ring and conjugation summary",
                    "donor-acceptor layout",
                    "planarity and torsion summary",
                    "compactness and contact proxies",
                    "conformer dispersion summary",
                ],
                focus_areas=focus_areas,
                unsupported_requests=_macro_unsupported_requests(task_instruction),
            ),
            capability_limit_note=(
                "Current macro capability is limited to deterministic low-cost single-molecule structural and geometry-proxy analysis. "
                "It cannot perform packing simulation, aggregate-state modeling, or global mechanism adjudication."
            ),
            expected_outputs=[
                "rotor topology",
                "ring and conjugation summary",
                "donor-acceptor layout",
                "planarity and torsion summary",
                "compactness and contact proxies",
                "conformer dispersion summary",
            ],
            failure_policy=(
                "If shared structure context is unavailable, return a local fallback report based on SMILES-only structural proxies."
            ),
        )


class TestMicroscopicReasoningBackend:
    def reason(self, rendered_prompt: Any, payload: dict[str, Any]) -> MicroscopicReasoningResponse:
        del rendered_prompt
        task_instruction = str(payload["task_instruction"])
        requested_deliverables = list(payload["requested_deliverables"])
        unsupported_requests = list(payload["unsupported_requests"])
        structure_context = payload["available_structure_context"]
        task_mode = payload["task_mode"]

        if structure_context.get("has_prepared_structure"):
            structure_strategy = "reuse_if_available_else_prepare_from_smiles"
            structure_note = "A prepared 3D structure is already available and should be reused if possible."
        else:
            structure_strategy = "prepare_from_smiles"
            structure_note = "No prepared 3D structure is available, so the run must start from SMILES-to-3D preparation."

        capability_limit_note = (
            "Current microscopic capability is bounded to a low-cost Amesp baseline only: structure preparation or reuse, "
            "low-cost S0 optimization, and bounded S1 vertical excitation. No global mechanism judgment is allowed."
        )
        if unsupported_requests:
            capability_limit_note = (
                f"{capability_limit_note} Unsupported requests are being conservatively contracted: "
                f"{'; '.join(unsupported_requests)}."
            )
        if task_mode == "targeted_follow_up":
            capability_limit_note = (
                f"{capability_limit_note} The requested targeted follow-up is reduced to the same baseline S0/S1 workflow "
                "in the current stage."
            )

        return MicroscopicReasoningResponse(
            task_understanding=(
                f"Use the Planner instruction to collect local microscopic evidence for the current working hypothesis "
                f"'{payload['current_hypothesis']}' without making any global mechanism judgment: {task_instruction}"
            ),
            reasoning_summary=(
                f"Interpret the Planner instruction as a bounded Amesp baseline task. {structure_note} "
                f"Requested local deliverables: {', '.join(requested_deliverables)}. {capability_limit_note}"
            ),
            execution_plan=MicroscopicReasoningPlanDraft(
                local_goal="Collect bounded low-cost microscopic evidence through the Amesp baseline workflow and return only local results.",
                requested_deliverables=requested_deliverables,
                structure_strategy=structure_strategy,
                step_sequence=["structure_prep", "s0_optimization", "s1_vertical_excitation"],
                unsupported_requests=unsupported_requests,
            ),
            capability_limit_note=capability_limit_note,
            expected_outputs=[
                "Low-cost S0 optimized geometry",
                "Low-cost S0 final energy",
                "S0 dipole",
                "S0 Mulliken charges",
                "S0 HOMO-LUMO gap",
                "S1 first excitation energy",
                "S1 first oscillator strength",
            ],
            failure_policy=(
                "If any Amesp step fails, return a local failed or partial report with the available artifacts and "
                "do not escalate into a global mechanism decision."
            ),
        )


class TestSharedStructureTool:
    name = "shared_structure_prep"

    def invoke(self, *, smiles: str, label: str, workdir: Path) -> SharedStructureContext:
        features = extract_smiles_features(smiles)
        workdir.mkdir(parents=True, exist_ok=True)
        xyz_path = workdir / "prepared_structure.xyz"
        sdf_path = workdir / "prepared_structure.sdf"
        summary_path = workdir / "structure_prep_summary.json"
        xyz_path.write_text("1\nX\nC 0.0 0.0 0.0\n", encoding="utf-8")
        sdf_path.write_text("fake sdf\n", encoding="utf-8")
        summary_path.write_text("{}", encoding="utf-8")
        aromatic_ring_count = max(1, features.aromatic_atom_count // 6) if features.aromatic_atom_count else max(
            1, features.ring_digit_count // 2
        )
        ring_system_count = max(1, aromatic_ring_count)
        rotatable_bond_count = max(1, features.branch_point_count // 2) if features.branch_point_count else 1
        return SharedStructureContext(
            input_smiles=smiles,
            canonical_smiles=smiles,
            charge=0,
            multiplicity=1,
            atom_count=max(12, features.length // 2),
            conformer_count=3,
            selected_conformer_id=1,
            prepared_xyz_path=str(xyz_path),
            prepared_sdf_path=str(sdf_path),
            summary_path=str(summary_path),
            rotatable_bond_count=rotatable_bond_count,
            aromatic_ring_count=aromatic_ring_count,
            ring_system_count=ring_system_count,
            hetero_atom_count=features.hetero_atom_count,
            branch_point_count=features.branch_point_count,
            donor_acceptor_partition_proxy=float(min(1, features.donor_acceptor_proxy)),
            planarity_proxy=round(min(1.0, max(0.2, features.conjugation_proxy / 10.0)), 6),
            compactness_proxy=round(max(0.0, 1.0 - min(features.length / 120.0, 1.0)), 6),
            torsion_candidate_count=rotatable_bond_count,
            principal_span_proxy=round(min(features.length / 10.0, 20.0), 6),
            conformer_dispersion_proxy=round(min(1.0, features.flexibility_proxy / 10.0), 6),
        )


class TestAmespTool:
    name = "amesp_baseline_microscopic"

    def __init__(self) -> None:
        self.called = False
        self.structure_sources: list[str] = []

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
    ) -> AmespBaselineRunResult:
        del progress_callback, round_index, case_id, current_hypothesis
        self.called = True
        self.structure_sources.append(plan.structure_source)
        features = extract_smiles_features(smiles)

        workdir.mkdir(parents=True, exist_ok=True)
        structure_dir = workdir / "structure_prep"
        structure_dir.mkdir(parents=True, exist_ok=True)
        xyz_path = structure_dir / "prepared_structure.xyz"
        sdf_path = structure_dir / "prepared_structure.sdf"
        summary_path = structure_dir / "structure_prep_summary.json"
        xyz_path.write_text("1\nX\nC 0.0 0.0 0.0\n", encoding="utf-8")
        sdf_path.write_text("fake sdf\n", encoding="utf-8")

        prepared = PreparedStructure(
            input_smiles=smiles,
            canonical_smiles=smiles,
            charge=0,
            multiplicity=1,
            heavy_atom_count=max(6, features.length // 5),
            atom_count=max(12, features.length // 2),
            conformer_count=3,
            selected_conformer_id=1,
            force_field="MMFF94",
            xyz_path=xyz_path,
            sdf_path=sdf_path,
            summary_path=summary_path,
        )
        summary_path.write_text(json.dumps(prepared.model_dump(mode="json")), encoding="utf-8")

        final_energy = round(-0.12 * features.length - 0.015 * features.conjugation_proxy, 6)
        gap = round(max(0.8, 6.5 - features.conjugation_proxy * 0.2), 6)
        excitation = round(min(4.5, 2.4 + features.conjugation_proxy * 0.05 + features.hetero_atom_count * 0.1), 4)
        oscillator = round(min(1.2, 0.25 + features.conjugation_proxy * 0.04 + features.hetero_atom_count * 0.02), 4)

        s0_xyz_path = workdir / "s0.xyz"
        s0_xyz_path.write_text("1\nX\nC 0.0 0.0 0.0\n", encoding="utf-8")
        return AmespBaselineRunResult(
            structure=prepared,
            s0=AmespGroundStateResult(
                final_energy_hartree=final_energy,
                dipole_debye=(0.0, 0.1, 0.0, 0.1),
                mulliken_charges=[-0.1, 0.1],
                homo_lumo_gap_ev=gap,
                geometry_atom_count=prepared.atom_count,
                geometry_xyz_path=str(s0_xyz_path),
                rmsd_from_prepared_structure_angstrom=0.1,
            ),
            s1=AmespExcitedStateResult(
                excited_states=[
                    AmespExcitedState(
                        state_index=1,
                        total_energy_hartree=final_energy + 0.1,
                        oscillator_strength=oscillator,
                        spin_square=0.0,
                        excitation_energy_ev=excitation,
                    )
                ],
                first_excitation_energy_ev=excitation,
                first_oscillator_strength=oscillator,
                state_count=1,
            ),
            raw_step_results={"s0_optimization": {"exit_code": 0}, "s1_vertical_excitation": {"exit_code": 0}},
            generated_artifacts={
                "prepared_xyz_path": str(xyz_path),
                "prepared_sdf_path": str(sdf_path),
                "prepared_summary_path": str(summary_path),
                "s0_aop_path": str(workdir / "s0.aop"),
            },
        )


def _macro_focus_areas(task_instruction: str) -> list[str]:
    lower = task_instruction.lower()
    focus_areas: list[str] = []
    mapping = {
        "rotor topology": ("rotatable", "rotation", "rotor", "rim", "rir"),
        "donor-acceptor layout": ("ict", "charge transfer", "donor", "acceptor", "tict"),
        "planarity and torsion": ("planarity", "torsion", "twist", "dihedral"),
        "compactness and contact proxies": ("cluster", "cte", "packing", "compact", "contact"),
        "conformer dispersion": ("conformer", "dispersion", "flexibility"),
    }
    for label, tokens in mapping.items():
        if any(token in lower for token in tokens):
            focus_areas.append(label)
    if not focus_areas:
        focus_areas.extend(["rotor topology", "ring and conjugation summary", "planarity and torsion"])
    return focus_areas


def _macro_unsupported_requests(task_instruction: str) -> list[str]:
    lower = task_instruction.lower()
    unsupported: list[str] = []
    mapping = {
        "aggregate-state simulation": ("aggregate", "packing simulation", "crystal"),
        "heavy conformer search": ("heavy conformer", "exhaustive conformer"),
        "global mechanism adjudication": ("dominant mechanism", "final mechanism"),
    }
    for label, tokens in mapping.items():
        if any(token in lower for token in tokens):
            unsupported.append(label)
    return unsupported


@pytest.fixture
def install_specialized_test_doubles(monkeypatch: pytest.MonkeyPatch) -> Callable[..., TestAmespTool]:
    def _install(
        *,
        shared_structure_tool: Any | None = None,
        amesp_tool: TestAmespTool | Any | None = None,
    ) -> TestAmespTool:
        fake_amesp = amesp_tool or TestAmespTool()

        from aie_mas.agents import macro as macro_module
        from aie_mas.agents import microscopic as microscopic_module

        monkeypatch.setattr(
            macro_module.MacroAgent,
            "_build_reasoning_backend",
            lambda self, config, llm_client: TestMacroReasoningBackend(),
        )
        monkeypatch.setattr(
            microscopic_module.MicroscopicAgent,
            "_build_reasoning_backend",
            lambda self, config, llm_client: TestMicroscopicReasoningBackend(),
        )

        def fake_build_toolset(config):
            del config
            return ToolSet(
                shared_structure_tool=shared_structure_tool or TestSharedStructureTool(),
                macro_tool=DeterministicMacroStructureTool(),
                verifier_tool=MockVerifierEvidenceTool(),
                amesp_micro_tool=fake_amesp,
            )

        monkeypatch.setattr(graph_builder, "build_toolset", fake_build_toolset)
        return fake_amesp

    return _install
