from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import pytest

from aie_mas.config import AieMasConfig
from aie_mas.agents.macro import MacroReasoningPlanDraft, MacroReasoningResponse
from aie_mas.agents.microscopic import (
    MicroscopicActionDecision,
    MicroscopicReasoningOutcome,
    MicroscopicReasoningPlanDraft,
    MicroscopicReasoningResponse,
    MicroscopicToolRequestDraft,
    compile_reasoning_response_to_execution_plan,
)
from aie_mas.chem.structure_prep import PreparedStructure
from aie_mas.graph import builder as graph_builder
from aie_mas.graph.state import (
    HypothesisEntry,
    MoleculeIdentityContext,
    PlannerDecision,
    SharedStructureContext,
    MicroscopicToolRequest,
)
from aie_mas.tools.amesp import (
    AmespBaselineRunResult,
    AmespExcitedState,
    AmespExcitedStateResult,
    AmespGroundStateResult,
)
from aie_mas.tools.factory import ToolSet
from aie_mas.tools.macro import DeterministicMacroStructureTool
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
    def reason(self, rendered_prompt: Any, payload: dict[str, Any]) -> MicroscopicReasoningOutcome:
        del rendered_prompt
        task_instruction = str(payload["task_instruction"])
        requested_deliverables = list(payload["requested_deliverables"])
        unsupported_requests = list(payload["unsupported_requests"])
        structure_context = payload["available_structure_context"]
        task_mode = payload["task_mode"]
        capability_route = _microscopic_capability_route(task_instruction, task_mode)
        capability_name = _microscopic_capability_name(capability_route, task_instruction)
        lower_instruction = task_instruction.lower()
        no_reoptimization = any(
            token in lower_instruction
            for token in (
                "no re-optimization",
                "no reoptimization",
                "no re-opt",
                "do not re-optimize",
                "do not reoptimize",
                "without re-optimization",
                "without reoptimization",
                "without full re-optimization",
            )
        )

        if structure_context.get("has_prepared_structure"):
            structure_strategy = "reuse_if_available_else_prepare_from_smiles"
            structure_note = "A prepared 3D structure is already available and should be reused if possible."
        else:
            structure_strategy = "prepare_from_smiles"
            structure_note = "No prepared 3D structure is available, so the run must start from SMILES-to-3D preparation."

        capability_limit_note = (
            "Current microscopic capability is bounded to low-cost Amesp routes only: baseline_bundle, "
            "conformer_bundle_follow_up, and torsion_snapshot_follow_up. No global mechanism judgment is allowed."
        )
        if unsupported_requests:
            capability_limit_note = (
                f"{capability_limit_note} Unsupported requests are being conservatively contracted: "
                f"{'; '.join(unsupported_requests)}."
            )

        response = MicroscopicReasoningResponse(
            task_understanding=(
                f"Use the Planner instruction to collect local microscopic evidence for the current working hypothesis "
                f"'{payload['current_hypothesis']}' without making any global mechanism judgment: {task_instruction}"
            ),
            reasoning_summary=(
                f"Interpret the Planner instruction as a bounded Amesp baseline task. {structure_note} "
                f"Requested local deliverables: {', '.join(requested_deliverables)}. {capability_limit_note}"
            ),
            execution_plan=MicroscopicReasoningPlanDraft(
                local_goal="Collect bounded low-cost microscopic evidence through the maximal executable Amesp route and return only local results.",
                requested_deliverables=requested_deliverables,
                capability_route=capability_route,
                requested_route_summary=f"Test reasoning selected route '{capability_route}' for: {task_instruction}",
                microscopic_tool_request=MicroscopicToolRequestDraft(
                    capability_name=capability_name,
                    perform_new_calculation=capability_name not in {"parse_snapshot_outputs", "unsupported_excited_state_relaxation"},
                    reuse_existing_artifacts_only=capability_name == "parse_snapshot_outputs",
                    optimize_ground_state=(
                        False
                        if capability_name in {"run_torsion_snapshots", "run_conformer_bundle"} and no_reoptimization
                        else None
                    ),
                    artifact_source_round=2 if "round_02" in task_instruction.lower() else None,
                    artifact_scope="torsion_snapshots" if capability_name in {"run_torsion_snapshots", "parse_snapshot_outputs"} else "conformer_bundle" if capability_name == "run_conformer_bundle" else None,
                    snapshot_count=2 if any(token in task_instruction.lower() for token in ("two torsion", "2 torsion", "±25", "+25", "-25")) else None,
                    angle_offsets_deg=[25.0, -25.0] if any(token in task_instruction.lower() for token in ("±25", "+25", "-25")) else [],
                    state_window=[1, 2, 3] if any(token in task_instruction.lower() for token in ("s1-s3", "s1–s3", "s1 to s3")) else [],
                    deliverables=requested_deliverables,
                    budget_profile=payload["budget_profile"],
                    requested_route_summary=f"Test reasoning selected capability '{capability_name}' for: {task_instruction}",
                ),
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
                "vertical-state manifold",
                "first bright-state energy",
                "first bright-state oscillator strength",
            ],
            failure_policy=(
                "If any Amesp step fails, return a local failed or partial report with the available artifacts and "
                "do not escalate into a global mechanism decision."
            ),
        )
        compiled_plan = compile_reasoning_response_to_execution_plan(
            response,
            payload=payload,
            config=AieMasConfig(),
        )
        tool_request = compiled_plan.microscopic_tool_request
        assert tool_request is not None
        action_decision = MicroscopicActionDecision(
            status="supported",
            execution_action=tool_request.capability_name,
            discovery_actions=[
                call.request.capability_name
                for call in compiled_plan.microscopic_tool_plan.calls
                if call.call_kind == "discovery"
            ],
            params={},
            unsupported_parts=list(compiled_plan.unsupported_requests),
            local_execution_rationale=response.reasoning_summary,
        )
        return MicroscopicReasoningOutcome(
            action_decision=action_decision,
            reasoning_response=response,
            compiled_execution_plan=compiled_plan,
            reasoning_parse_mode="legacy_json_fallback",
            reasoning_contract_mode="legacy_json_fallback",
            reasoning_contract_errors=[],
        )


def _microscopic_capability_route(task_instruction: str, task_mode: str) -> str:
    lower_instruction = task_instruction.lower()
    if "list_artifact_bundle_members" in task_instruction:
        return "artifact_parse_only"
    if "run_targeted_transition_dipole_analysis" in task_instruction:
        return "targeted_property_follow_up"
    if "run_ris_state_characterization" in task_instruction:
        return "targeted_property_follow_up"
    if "run_targeted_charge_analysis" in task_instruction:
        return "targeted_property_follow_up"
    if "run_targeted_localized_orbital_analysis" in task_instruction:
        return "targeted_property_follow_up"
    if "run_targeted_natural_orbital_analysis" in task_instruction:
        return "targeted_property_follow_up"
    if "run_targeted_density_population_analysis" in task_instruction:
        return "targeted_property_follow_up"
    if "run_targeted_state_characterization" in task_instruction:
        return "targeted_property_follow_up"
    if task_mode == "baseline_s0_s1":
        return "baseline_bundle"
    if (
        "parse_snapshot_outputs" in lower_instruction
        or (
            any(token in lower_instruction for token in ("reuse existing", "reuse round_", "existing artifacts", "parse-only", "do not run new calculations"))
            and any(token in lower_instruction for token in ("artifact", "output", "snapshot"))
        )
    ):
        return "artifact_parse_only"
    if "torsion_snapshot_follow_up" in lower_instruction:
        return "torsion_snapshot_follow_up"
    if "conformer_bundle_follow_up" in lower_instruction or "conformer" in lower_instruction:
        return "conformer_bundle_follow_up"
    if (
        "excited_state_relaxation_follow_up" in lower_instruction
        or "excited-state relaxation" in lower_instruction
        or "excited-state geometry relaxation" in lower_instruction
        or "excited-state geometry" in lower_instruction
        or "s1 relaxation" in lower_instruction
    ):
        return "excited_state_relaxation_follow_up"
    if any(token in lower_instruction for token in ("torsion", "dihedral", "twist", "rotor")):
        return "torsion_snapshot_follow_up"
    return "conformer_bundle_follow_up"


def _microscopic_capability_name(capability_route: str, task_instruction: str = "") -> str:
    for capability_name in (
        "list_artifact_bundle_members",
        "run_targeted_transition_dipole_analysis",
        "run_ris_state_characterization",
        "run_targeted_charge_analysis",
        "run_targeted_localized_orbital_analysis",
        "run_targeted_natural_orbital_analysis",
        "run_targeted_density_population_analysis",
        "run_targeted_state_characterization",
        "extract_geometry_descriptors_from_bundle",
    ):
        if capability_name in task_instruction:
            return capability_name
    if capability_route == "baseline_bundle":
        return "run_baseline_bundle"
    if capability_route == "conformer_bundle_follow_up":
        return "run_conformer_bundle"
    if capability_route == "torsion_snapshot_follow_up":
        return "run_torsion_snapshots"
    if capability_route == "artifact_parse_only":
        return "parse_snapshot_outputs"
    return "unsupported_excited_state_relaxation"


class TestPlannerBackend:
    def plan_initial(self, rendered_prompt: Any, payload: dict[str, Any]) -> dict[str, Any]:
        del rendered_prompt
        hypothesis_pool = [
            HypothesisEntry(
                name="neutral aromatic",
                confidence=0.7,
                rationale="Test planner starts from a conservative neutral-aromatic hypothesis.",
                candidate_strength="strong",
            ),
            HypothesisEntry(
                name="ICT",
                confidence=0.24,
                rationale="Secondary test-only alternative.",
                candidate_strength="weak",
            ),
        ]
        task_instruction = "Dispatch first-round specialized macro and microscopic tasks for the current hypothesis."
        decision = PlannerDecision(
            diagnosis="The first round should gather macro structural evidence and bounded microscopic S0/S1 evidence.",
            action="macro_and_microscopic",
            current_hypothesis=hypothesis_pool[0].name,
            confidence=0.7,
            planned_agents=["macro", "microscopic"],
            task_instruction=task_instruction,
            agent_task_instructions={
                "macro": (
                    f"Assess macro-level structural evidence relevant to the current working hypothesis "
                    f"'{hypothesis_pool[0].name}'. Reuse the shared prepared structure context when available."
                ),
                "microscopic": (
                    f"Run the first-round low-cost S0/S1 microscopic baseline task for the current working hypothesis "
                    f"'{hypothesis_pool[0].name}'. Reuse the shared prepared structure context when available."
                ),
            },
            hypothesis_uncertainty_note="The leading hypothesis is still provisional before internal evidence collection.",
            capability_assessment="Current specialized agents can collect bounded internal evidence only.",
            stagnation_assessment="No stagnation is present in the initial round.",
        )
        raw_response = {
            "hypothesis_pool": [entry.model_dump(mode="json") for entry in hypothesis_pool],
            "current_hypothesis": decision.current_hypothesis,
            "confidence": decision.confidence,
            "diagnosis": decision.diagnosis,
            "action": decision.action,
            "task_instruction": decision.task_instruction,
            "agent_task_instructions": dict(decision.agent_task_instructions),
            "hypothesis_uncertainty_note": decision.hypothesis_uncertainty_note,
            "capability_assessment": decision.capability_assessment,
        }
        return {
            "hypothesis_pool": hypothesis_pool,
            "decision": decision,
            "raw_response": raw_response,
            "normalized_response": {"decision": decision.model_dump(mode="json")},
        }

    def plan_diagnosis(self, rendered_prompt: Any, payload: dict[str, Any]) -> dict[str, Any]:
        del rendered_prompt
        current_hypothesis = str(payload["current_hypothesis"])
        evidence_summary = "Macro and microscopic local evidence were collected."
        main_gap = "External verifier evidence is still needed before closure."
        task_instruction = (
            f"Retrieve external supervision evidence for the current working hypothesis '{current_hypothesis}' "
            f"and clarify the current gap: {main_gap}"
        )
        decision = PlannerDecision(
            diagnosis=(
                f"The current leading hypothesis remains {current_hypothesis}. The latest internal evidence does not "
                "justify closure yet, so verifier is the best next step."
            ),
            action="verifier",
            current_hypothesis=current_hypothesis,
            confidence=float(payload["current_confidence"] or 0.7),
            needs_verifier=True,
            finalize=False,
            planned_agents=["verifier"],
            task_instruction=task_instruction,
            agent_task_instructions={"verifier": task_instruction},
            hypothesis_uncertainty_note="Internal evidence is useful but not yet enough for closure.",
            capability_assessment="Internal agents can provide only bounded evidence; verifier is needed for validation.",
            stagnation_assessment="No stagnation is present yet.",
            contraction_reason="Use verifier once internal evidence has been collected.",
            information_gain_assessment="The first round added useful internal evidence.",
            gap_trend="The main gap is shrinking.",
            stagnation_detected=False,
        )
        raw_response = {
            "diagnosis": decision.diagnosis,
            "action": decision.action,
            "current_hypothesis": decision.current_hypothesis,
            "confidence": decision.confidence,
            "needs_verifier": True,
            "finalize": False,
            "task_instruction": task_instruction,
            "agent_task_instructions": {"verifier": task_instruction},
            "hypothesis_uncertainty_note": decision.hypothesis_uncertainty_note,
            "capability_assessment": decision.capability_assessment,
            "stagnation_assessment": decision.stagnation_assessment,
            "contraction_reason": decision.contraction_reason,
            "evidence_summary": evidence_summary,
            "main_gap": main_gap,
            "conflict_status": "none",
            "information_gain_assessment": decision.information_gain_assessment,
            "gap_trend": decision.gap_trend,
            "stagnation_detected": False,
            "capability_lesson_candidates": [],
        }
        return {
            "decision": decision,
            "evidence_summary": evidence_summary,
            "main_gap": main_gap,
            "conflict_status": "none",
            "hypothesis_uncertainty_note": decision.hypothesis_uncertainty_note,
            "capability_assessment": decision.capability_assessment,
            "stagnation_assessment": decision.stagnation_assessment,
            "contraction_reason": decision.contraction_reason,
            "information_gain_assessment": decision.information_gain_assessment,
            "gap_trend": decision.gap_trend,
            "raw_response": raw_response,
            "normalized_response": {"decision": decision.model_dump(mode="json")},
        }

    def plan_reweight_or_finalize(self, rendered_prompt: Any, payload: dict[str, Any]) -> dict[str, Any]:
        del rendered_prompt
        current_hypothesis = str(payload["current_hypothesis"])
        verifier_report = payload.get("verifier_report") or {}
        evidence_summary = str(verifier_report.get("result_summary") or "Verifier evidence aligns with the current hypothesis.")
        decision = PlannerDecision(
            diagnosis=(
                f"Planner interpretation of verifier evidence supports the current hypothesis {current_hypothesis}. "
                "The case can now be finalized."
            ),
            action="finalize",
            current_hypothesis=current_hypothesis,
            confidence=min(0.95, float(payload["current_confidence"] or 0.7) + 0.08),
            needs_verifier=False,
            finalize=True,
            planned_agents=[],
            hypothesis_uncertainty_note="Residual uncertainty remains limited and acceptable at closure.",
            final_hypothesis_rationale=(
                f"The mechanism is finalized as {current_hypothesis} because the internal evidence chain and verifier "
                f"evidence align in this run. Key support: {evidence_summary}"
            ),
            capability_assessment="Verifier evidence closes the remaining gap under the current bounded workflow.",
            stagnation_assessment="No stagnation remains after verifier support.",
            contraction_reason="Conservatively stop because further internal expansion is unnecessary.",
            information_gain_assessment="Verifier evidence provides the final information needed for closure.",
            gap_trend="The main gap is closed.",
            stagnation_detected=False,
        )
        raw_response = {
            "diagnosis": decision.diagnosis,
            "action": "finalize",
            "current_hypothesis": decision.current_hypothesis,
            "confidence": decision.confidence,
            "needs_verifier": False,
            "finalize": True,
            "task_instruction": None,
            "agent_task_instructions": {},
            "hypothesis_uncertainty_note": decision.hypothesis_uncertainty_note,
            "final_hypothesis_rationale": decision.final_hypothesis_rationale,
            "capability_assessment": decision.capability_assessment,
            "stagnation_assessment": decision.stagnation_assessment,
            "contraction_reason": decision.contraction_reason,
            "evidence_summary": evidence_summary,
            "main_gap": "No critical evidence gap remains in the current workflow.",
            "conflict_status": "none",
            "information_gain_assessment": decision.information_gain_assessment,
            "gap_trend": decision.gap_trend,
            "stagnation_detected": False,
            "capability_lesson_candidates": [],
        }
        return {
            "decision": decision,
            "evidence_summary": evidence_summary,
            "main_gap": "No critical evidence gap remains in the current workflow.",
            "conflict_status": "none",
            "hypothesis_uncertainty_note": decision.hypothesis_uncertainty_note,
            "final_hypothesis_rationale": decision.final_hypothesis_rationale,
            "capability_assessment": decision.capability_assessment,
            "stagnation_assessment": decision.stagnation_assessment,
            "contraction_reason": decision.contraction_reason,
            "information_gain_assessment": decision.information_gain_assessment,
            "gap_trend": decision.gap_trend,
            "raw_response": raw_response,
            "normalized_response": {"decision": decision.model_dump(mode="json")},
        }


class TestSharedStructureTool:
    name = "shared_structure_prep"

    def invoke(self, *, smiles: str, label: str, workdir: Path) -> dict[str, object]:
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
        return {
            "shared_structure_context": SharedStructureContext(
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
            ),
            "molecule_identity_context": MoleculeIdentityContext(
                input_smiles=smiles,
                canonical_smiles=smiles,
                molecular_formula="C10H10",
                inchi="InChI=1S/test",
                inchikey="TEST-INCHIKEY",
            ),
            "molecule_identity_status": "ready",
            "molecule_identity_error": None,
        }


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
        del progress_callback, case_id, current_hypothesis
        self.called = True
        self.structure_sources.append(plan.structure_source)
        tool_request = plan.microscopic_tool_request
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
            route=plan.capability_route,
            executed_capability=tool_request.capability_name,
            performed_new_calculations=tool_request.perform_new_calculation,
            reused_existing_artifacts=tool_request.reuse_existing_artifacts_only,
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
                    ),
                    AmespExcitedState(
                        state_index=2,
                        total_energy_hartree=final_energy + 0.12,
                        oscillator_strength=0.02,
                        spin_square=0.0,
                        excitation_energy_ev=round(excitation + 0.18, 4),
                    )
                ],
                first_excitation_energy_ev=excitation,
                first_oscillator_strength=oscillator,
                state_count=2,
            ),
            route_records=[],
            route_summary={},
            raw_step_results={"s0_optimization": {"exit_code": 0}, "s1_vertical_excitation": {"exit_code": 0}},
            generated_artifacts={
                "prepared_xyz_path": str(xyz_path),
                "prepared_sdf_path": str(sdf_path),
                "prepared_summary_path": str(summary_path),
                "s0_aop_path": str(workdir / "s0.aop"),
                "source_round": round_index,
            },
        )


class TestVerifierTool:
    name = "verifier_evidence_lookup"

    def invoke(
        self,
        *,
        smiles: str,
        current_hypothesis: str,
        task_received: str,
        main_gap: str,
        molecule_identity_context: MoleculeIdentityContext | None,
        latest_macro_report,
        latest_microscopic_report,
    ) -> dict[str, Any]:
        del smiles, task_received, main_gap, molecule_identity_context, latest_macro_report, latest_microscopic_report
        return {
            "status": "success",
            "source_count": 1,
            "evidence_cards": [
                {
                    "card_id": "test-verifier-card",
                    "source": "test_source",
                    "title": "Test verifier evidence",
                    "doi": None,
                    "url": None,
                    "observation": (
                        f"External material in this test fixture discusses the current hypothesis "
                        f"{current_hypothesis} alongside related AIE context."
                    ),
                    "topic_tags": ["restriction"],
                    "evidence_kind": "external_summary",
                    "why_relevant": "Test-only verifier evidence card.",
                    "query_group": "similar_family",
                    "match_level": "same_family",
                    "mechanism_claim": None,
                    "experimental_context": None,
                }
            ],
            "queried_hypothesis": current_hypothesis,
            "retrieval_note": "Test-only verifier retrieval completed.",
            "raw_response": {"evidence_cards": 1},
            "queries_executed": [{"query_group": "similar_family", "query": "test query"}],
            "query_groups_attempted": ["exact_identity", "similar_family", "mechanistic_discriminator"],
            "query_groups_with_hits": ["similar_family"],
        }


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
        from aie_mas.agents import planner as planner_module

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
        monkeypatch.setattr(
            planner_module.PlannerAgent,
            "_build_backend",
            lambda self, config, llm_client: TestPlannerBackend(),
        )

        def fake_build_toolset(config):
            del config
            return ToolSet(
                shared_structure_tool=shared_structure_tool or TestSharedStructureTool(),
                macro_tool=DeterministicMacroStructureTool(),
                verifier_tool=TestVerifierTool(),
                amesp_micro_tool=fake_amesp,
            )

        monkeypatch.setattr(graph_builder, "build_toolset", fake_build_toolset)
        return fake_amesp

    return _install
