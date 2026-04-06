from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Optional

from aie_mas.config import AieMasConfig
from aie_mas.graph.state import SharedStructureContext, WorkflowProgressEvent
from aie_mas.llm.openai_compatible import OpenAICompatibleMicroscopicClient
from aie_mas.tools.amesp import (
    AmespExecutionError,
    AmespMicroscopicTool,
    render_amesp_action_registry,
    render_amesp_capability_registry,
    render_amesp_interface_catalog,
    render_reasoned_microscopic_examples,
    render_registry_backed_microscopic_examples,
)
from aie_mas.utils.prompts import PromptRepository

from .compiler import _default_prompt_repository
from .executor import MicroscopicExecutorMixin
from .interpreter import MicroscopicReasoningBackend, OpenAIMicroscopicReasoningBackend
from .reporting import MicroscopicReportingMixin


class MicroscopicAgent(MicroscopicExecutorMixin, MicroscopicReportingMixin):
    def __init__(
        self,
        amesp_tool: Optional[AmespMicroscopicTool] = None,
        *,
        prompts: Optional[PromptRepository] = None,
        tools_work_dir: Optional[Path] = None,
        config: Optional[AieMasConfig] = None,
        llm_client: Optional[OpenAICompatibleMicroscopicClient] = None,
        progress_callback: Optional[Callable[[WorkflowProgressEvent], None]] = None,
    ) -> None:
        self._amesp_tool = amesp_tool
        self._prompts = prompts or _default_prompt_repository()
        self._tools_work_dir = tools_work_dir
        self._config = config or AieMasConfig()
        self._reasoning_backend = self._build_reasoning_backend(self._config, llm_client)
        self._progress_callback = progress_callback

    def _emit_probe(
        self,
        *,
        round_index: int,
        case_id: Optional[str],
        current_hypothesis: Optional[str],
        stage: str,
        status: str,
        details: dict[str, Any],
    ) -> None:
        if self._progress_callback is None:
            return
        event: WorkflowProgressEvent = {
            "phase": "probe",
            "node": "run_microscopic",
            "round": round_index,
            "agent": "microscopic",
            "case_id": case_id,
            "current_hypothesis": current_hypothesis,
            "details": {
                "probe_stage": stage,
                "probe_status": status,
                **details,
            },
        }
        self._progress_callback(event)

    def _build_reasoning_backend(
        self,
        config: AieMasConfig,
        llm_client: Optional[OpenAICompatibleMicroscopicClient],
    ) -> MicroscopicReasoningBackend:
        return OpenAIMicroscopicReasoningBackend(config, client=llm_client)

    def _build_reasoning_payload(
        self,
        *,
        current_hypothesis: str,
        task_instruction: str,
        task_spec: MicroscopicTaskSpec,
        recent_rounds_context: list[dict[str, object]],
        available_artifacts: dict[str, Any],
        shared_structure_context: Optional[SharedStructureContext],
        round_index: int,
    ) -> dict[str, Any]:
        requested_deliverables = self._requested_deliverables(task_instruction, task_spec)
        unsupported_requests = self._unsupported_requests(task_instruction, task_spec)
        registry_examples = render_registry_backed_microscopic_examples()
        reasoned_examples = render_reasoned_microscopic_examples()
        return {
            "current_hypothesis": current_hypothesis,
            "task_instruction": task_instruction,
            "task_mode": task_spec.mode,
            "current_round_index": round_index,
            "requested_deliverables": requested_deliverables,
            "unsupported_requests": unsupported_requests,
            "budget_profile": self._config.microscopic_budget_profile,
            "amesp_interface_catalog": render_amesp_interface_catalog(),
            "action_registry": render_amesp_action_registry(),
            "baseline_action_card_example": registry_examples["baseline"],
            "torsion_action_card_example": registry_examples["torsion"],
            "targeted_charge_analysis_action_card_example": registry_examples["targeted_charge_analysis"],
            "targeted_localized_orbital_analysis_action_card_example": registry_examples[
                "targeted_localized_orbital_analysis"
            ],
            "targeted_natural_orbital_analysis_action_card_example": registry_examples[
                "targeted_natural_orbital_analysis"
            ],
            "targeted_density_population_analysis_action_card_example": registry_examples[
                "targeted_density_population_analysis"
            ],
            "targeted_transition_dipole_analysis_action_card_example": registry_examples[
                "targeted_transition_dipole_analysis"
            ],
            "ris_state_characterization_action_card_example": registry_examples[
                "ris_state_characterization"
            ],
            "targeted_state_characterization_action_card_example": registry_examples["targeted_state_characterization"],
            "baseline_reasoned_action_example": reasoned_examples["baseline"],
            "torsion_reasoned_action_example": reasoned_examples["torsion"],
            "targeted_charge_analysis_reasoned_action_example": reasoned_examples["targeted_charge_analysis"],
            "targeted_localized_orbital_analysis_reasoned_action_example": reasoned_examples[
                "targeted_localized_orbital_analysis"
            ],
            "targeted_natural_orbital_analysis_reasoned_action_example": reasoned_examples[
                "targeted_natural_orbital_analysis"
            ],
            "targeted_density_population_analysis_reasoned_action_example": reasoned_examples[
                "targeted_density_population_analysis"
            ],
            "targeted_transition_dipole_analysis_reasoned_action_example": reasoned_examples[
                "targeted_transition_dipole_analysis"
            ],
            "ris_state_characterization_reasoned_action_example": reasoned_examples[
                "ris_state_characterization"
            ],
            "targeted_state_characterization_reasoned_action_example": reasoned_examples["targeted_state_characterization"],
            "capability_registry": render_amesp_capability_registry(),
            "recent_rounds_context": recent_rounds_context,
            "available_structure_context": self._available_structure_context(
                available_artifacts,
                shared_structure_context=shared_structure_context,
            ),
            "shared_structure_context": (
                shared_structure_context.model_dump(mode="json")
                if shared_structure_context is not None
                else None
            ),
            "runtime_context": self._runtime_context_summary(),
        }

    def _available_structure_context(
        self,
        available_artifacts: dict[str, Any],
        *,
        shared_structure_context: Optional[SharedStructureContext],
    ) -> dict[str, Any]:
        context = {
            "has_prepared_structure": False,
            "prepared_xyz_path": None,
            "prepared_summary_path": None,
            "prepared_atom_count": None,
            "prepared_charge": None,
            "prepared_multiplicity": None,
            "source": "missing",
        }
        if shared_structure_context is not None:
            context["has_prepared_structure"] = True
            context["prepared_xyz_path"] = shared_structure_context.prepared_xyz_path
            context["prepared_summary_path"] = shared_structure_context.summary_path
            context["prepared_atom_count"] = shared_structure_context.atom_count
            context["prepared_charge"] = shared_structure_context.charge
            context["prepared_multiplicity"] = shared_structure_context.multiplicity
            context["source"] = "shared_structure_context"
            return context
        summary_path = available_artifacts.get("prepared_summary_path")
        xyz_path = available_artifacts.get("prepared_xyz_path")
        if not summary_path or not xyz_path:
            return context
        summary_path_obj = Path(str(summary_path))
        xyz_path_obj = Path(str(xyz_path))
        if not summary_path_obj.exists() or not xyz_path_obj.exists():
            return context
        context["has_prepared_structure"] = True
        context["prepared_xyz_path"] = str(xyz_path_obj)
        context["prepared_summary_path"] = str(summary_path_obj)
        try:
            summary_payload = json.loads(summary_path_obj.read_text(encoding="utf-8"))
        except Exception:
            return context
        context["prepared_atom_count"] = summary_payload.get("atom_count")
        context["prepared_charge"] = summary_payload.get("charge")
        context["prepared_multiplicity"] = summary_payload.get("multiplicity")
        context["source"] = "available_artifacts"
        return context

    def _runtime_context_summary(self) -> dict[str, Any]:
        return {
            "microscopic_backend": self._config.microscopic_backend,
            "amesp_binary_path": str(self._config.amesp_binary_path) if self._config.amesp_binary_path else None,
            "supports_real_amesp": self._amesp_tool is not None,
            "baseline_policy": (
                "baseline-first must stay low-cost; do not default to heavy exhaustive DFT geometry optimization for large systems"
            ),
            "supported_scope": [
                "baseline_bundle: low-cost aTB S0 optimization plus vertical excited-state manifold",
                (
                    "conformer_bundle_follow_up: bounded conformer sensitivity route "
                    f"(max {self._config.amesp_follow_up_max_conformers} conformers)"
                ),
                (
                    "torsion_snapshot_follow_up: bounded torsion sensitivity route "
                    f"(max {self._config.amesp_follow_up_max_torsion_snapshots_total} snapshots)"
                ),
            ],
            "unsupported_scope": [
                "heavy full-DFT geometry optimization as a default first-round baseline",
                "excited-state relaxation follow-up before route validation",
                "scan",
                "TS",
                "IRC",
                "solvent",
                "SOC",
                "NAC",
                "AIMD",
            ],
            "shared_structure_policy": (
                "prefer shared prepared structure context; only compatibility paths may fall back to private structure preparation"
            ),
            "budget_profile": self._config.microscopic_budget_profile,
            "vertical_state_count_default": self._config.amesp_s1_nstates,
        }

    def _resolve_workdir(self, *, case_id: str, round_index: int) -> Path:
        base_dir = self._tools_work_dir or (Path.cwd() / "var" / "runtime" / "tools")
        return base_dir / "microscopic" / case_id / f"round_{round_index:02d}"

    def _requested_deliverables(
        self,
        task_received: str,
        task_spec: MicroscopicTaskSpec,
    ) -> list[str]:
        lower_instruction = task_received.lower()
        if task_spec.mode == "baseline_s0_s1":
            deliverables = [
                "low-cost aTB S0 geometry optimization",
                "vertical excited-state manifold characterization",
            ]
            if "dipole" in lower_instruction:
                deliverables.append("dipole summary")
            if any(
                token in lower_instruction
                for token in (
                    "transition dipole",
                    "transition-dipole",
                    "excited-to-excited dipole",
                    "ground-to-excited dipole",
                    "excdip",
                )
            ):
                deliverables.append("transition-dipole summary")
            if "charge" in lower_instruction:
                deliverables.append("Mulliken charge summary")
            if "hirshfeld" in lower_instruction:
                deliverables.append("Hirshfeld charge summary")
            if any(token in lower_instruction for token in ("localized orbital", "localized-orbital", "lmo", "pipek-mezey", "pipek mezey")):
                deliverables.append("localized-orbital summary")
            if any(token in lower_instruction for token in ("natural orbital", "natural-orbital", "natorb")):
                deliverables.append("natural-orbital summary")
            if any(token in lower_instruction for token in ("density matrix", "gross orbital population", "gross orbital populations")):
                deliverables.append("density/population summary")
            if any(token in lower_instruction for token in ("bond order", "bond-order", "mayer")):
                deliverables.append("Mayer bond-order summary")
            if any(token in lower_instruction for token in ("ris", "tda-ris", "td-ris")):
                deliverables.append("RIS state-characterization summary")
            if any(token in lower_instruction for token in ("homo-lumo", "homo lumo", "gap")):
                deliverables.append("HOMO-LUMO gap summary")
            if any(
                token in lower_instruction
                for token in (
                    "ct descriptor",
                    "ct descriptors",
                    "charge-transfer",
                    "charge transfer",
                    "electron-hole",
                    "electron hole",
                    "ct distance",
                )
            ):
                deliverables.append("CT descriptor availability note")
            return list(dict.fromkeys(deliverables))
        deliverables: list[str] = []
        torsion_like = any(
            token in lower_instruction
            for token in ("torsion", "dihedral", "twist", "rotor", "rotation sensitivity", "rotational sensitivity")
        )
        if any(token in lower_instruction for token in ("s0", "ground-state", "ground state", "opt")):
            deliverables.append("low-cost aTB S0 geometry optimization")
        if any(token in lower_instruction for token in ("s1", "excited", "oscillator", "vertical")):
            deliverables.append("vertical excited-state manifold characterization")
        if "dipole" in lower_instruction:
            deliverables.append("dipole summary")
        if any(
            token in lower_instruction
            for token in (
                "transition dipole",
                "transition-dipole",
                "excited-to-excited dipole",
                "ground-to-excited dipole",
                "excdip",
            )
        ):
            deliverables.append("transition-dipole summary")
        if "charge" in lower_instruction:
            deliverables.append("Mulliken charge summary")
        if "hirshfeld" in lower_instruction:
            deliverables.append("Hirshfeld charge summary")
        if any(token in lower_instruction for token in ("localized orbital", "localized-orbital", "lmo", "pipek-mezey", "pipek mezey")):
            deliverables.append("localized-orbital summary")
        if any(token in lower_instruction for token in ("natural orbital", "natural-orbital", "natorb")):
            deliverables.append("natural-orbital summary")
        if any(token in lower_instruction for token in ("density matrix", "gross orbital population", "gross orbital populations")):
            deliverables.append("density/population summary")
        if any(token in lower_instruction for token in ("bond order", "bond-order", "mayer")):
            deliverables.append("Mayer bond-order summary")
        if any(token in lower_instruction for token in ("ris", "tda-ris", "td-ris")):
            deliverables.append("RIS state-characterization summary")
        if any(token in lower_instruction for token in ("conformer", "conformational")):
            deliverables.append("conformer-sensitivity summary")
        if torsion_like:
            deliverables.append("torsion-sensitivity summary")
        if not deliverables:
            deliverables.extend(
                [
                    "low-cost aTB S0 geometry optimization",
                    "vertical excited-state manifold characterization",
                ]
            )
        return deliverables

    def _unsupported_requests(
        self,
        task_received: str,
        task_spec: MicroscopicTaskSpec,
    ) -> list[str]:
        del task_spec
        lower_instruction = task_received.lower()
        unsupported: list[str] = []
        if "scan" in lower_instruction and any(
            token in lower_instruction for token in ("torsion", "dihedral", "rotation", "rotor")
        ):
            unsupported.append("torsion scan")
        keyword_mapping = {
            "heavy full-DFT geometry optimization": (
                re.compile(r"\bfull[\s-]?dft\b"),
                re.compile(r"\bexhaustive geometry optimization\b"),
            ),
            "transition-state optimization": (
                re.compile(r"\btransition[\s-]?state\b"),
                re.compile(r"\bts optimization\b"),
                re.compile(r"\btransition[\s-]?state optimization\b"),
            ),
            "IRC": (re.compile(r"\birc\b"),),
            "solvent model": (
                re.compile(r"\bsolvent model\b"),
                re.compile(r"\bcpcm\b"),
                re.compile(r"\bcosmo\b"),
            ),
            "SOC/NAC analysis": (
                re.compile(r"\bsoc\b"),
                re.compile(r"\bnac\b"),
            ),
            "AIMD": (
                re.compile(r"\baimd\b"),
                re.compile(r"\bab initio molecular dynamics\b"),
            ),
        }
        for label, patterns in keyword_mapping.items():
            if any(pattern.search(lower_instruction) for pattern in patterns):
                unsupported.append(label)
        unsupported.extend(self._registry_blocked_requests(task_received))
        return list(dict.fromkeys(unsupported))

    def _registry_blocked_requests(
        self,
        task_received: str,
    ) -> list[str]:
        del task_received
        return []

    def _has_reusable_structure(self, available_artifacts: dict[str, Any]) -> bool:
        summary_path = available_artifacts.get("prepared_summary_path")
        xyz_path = available_artifacts.get("prepared_xyz_path")
        return bool(summary_path and xyz_path and Path(str(summary_path)).exists() and Path(str(xyz_path)).exists())

    def _recent_context_note(self, recent_rounds_context: list[dict[str, object]]) -> str:
        if not recent_rounds_context:
            return "No prior microscopic round context is available."
        latest = recent_rounds_context[-1]
        return (
            f"Recent round {latest.get('round_id')} used action '{latest.get('action_taken')}' "
            f"and left the gap '{latest.get('main_gap')}'."
        )

    def _capability_scope_text(self) -> str:
        return (
            "Current microscopic capability is Amesp low-cost multi-route execution with protocolized capabilities: "
            "run_baseline_bundle, run_conformer_bundle, run_torsion_snapshots, run_targeted_charge_analysis, "
            "run_targeted_localized_orbital_analysis, run_targeted_natural_orbital_analysis, "
            "run_targeted_density_population_analysis, run_targeted_transition_dipole_analysis, "
            "run_ris_state_characterization, run_targeted_state_characterization, parse_snapshot_outputs, "
            "extract_ct_descriptors_from_bundle, extract_geometry_descriptors_from_bundle, and "
            "inspect_raw_artifact_bundle. "
            "unsupported_excited_state_relaxation is a fail-fast unsupported capability and does not execute."
        )

    def _structure_source_note(
        self,
        structure_source: str,
        available_artifacts: dict[str, Any],
        *,
        shared_structure_context: Optional[SharedStructureContext],
    ) -> str:
        if structure_source == "existing_prepared_structure" and shared_structure_context is not None:
            return (
                "Reuse the shared prepared 3D structure context that is already available for this case at "
                f"{shared_structure_context.prepared_xyz_path}."
            )
        if structure_source == "existing_prepared_structure":
            return "Reuse the previously prepared 3D structure artifacts that are already available for this case."
        if available_artifacts.get("prepared_xyz_path"):
            return (
                "A previous prepared structure was referenced but is not reusable from disk, so a fresh 3D structure "
                "will be generated from the input SMILES before the bounded Amesp route is executed."
            )
        return "Prepare a fresh 3D structure from the input SMILES before running the bounded Amesp route."

    def _unsupported_requests_note(self, unsupported_requests: list[str]) -> str:
        if not unsupported_requests:
            return "No unsupported local request was detected."
        return "; ".join(unsupported_requests)

    def _registry_completion_code_for_parse_error(
        self,
        contract_errors: list[str],
    ) -> MicroscopicCompletionReasonCode:
        registry_markers = (
            "unknown execution_action",
            "not allowed for execution_action",
            "python-owned and must not be authored",
            "invalid discovery action",
            "placeholder target values are not allowed for param.",
            "registry-backed action card",
        )
        joined = " ".join(contract_errors).lower()
        if any(marker in joined for marker in registry_markers):
            return "action_not_supported_by_registry"
        return "protocol_parse_failed"

    def _registry_handshake_reason(
        self,
        *,
        completion_reason_code: Optional[MicroscopicCompletionReasonCode],
        missing_deliverables: list[str],
        route_summary: Optional[dict[str, Any]],
        registry_validation_errors: list[str],
    ) -> Optional[str]:
        if completion_reason_code == "action_not_supported_by_registry":
            return "action_not_supported_by_registry"
        if completion_reason_code == "capability_unsupported":
            return "microscopic_capability_unsupported"
        if registry_validation_errors:
            return "registry_validation_failed"
        missing_lower = [item.lower() for item in missing_deliverables]
        if any(
            "ct/localization proxy" in item
            or "dominant transition" in item
            or "intramolecular h-bond" in item
            or "local planarity proxy" in item
            for item in missing_lower
        ):
            return "required_registry_observables_unavailable"
        if isinstance(route_summary, dict) and route_summary.get("ct_proxy_availability") == "not_available":
            return "required_registry_observables_unavailable"
        if isinstance(route_summary, dict) and route_summary.get("geometry_proxy_availability") == "not_available":
            return "required_registry_observables_unavailable"
        return None

    def _remaining_uncertainty_text(
        self,
        unsupported_requests: list[str],
        task_mode: str,
        capability_route: MicroscopicCapabilityRoute,
        executed_capability: str | None = None,
    ) -> str:
        limitation_bits = [
            f"this bounded Amesp route '{capability_route}' does not adjudicate the global mechanism",
            "it does not execute full-DFT or heavy excited-state optimization",
        ]
        if capability_route == "artifact_parse_only":
            limitation_bits.append("it only parses existing artifacts and cannot create new microscopic evidence")
        if unsupported_requests:
            limitation_bits.append(
                "it also leaves unsupported local requests unresolved: " + "; ".join(unsupported_requests)
            )
        if task_mode == "targeted_follow_up":
            if executed_capability:
                limitation_bits.append(
                    f"targeted follow-up for microscopic capability '{executed_capability}' remains bounded by current Amesp route availability and resource limits"
                )
            else:
                limitation_bits.append(
                    "targeted follow-up remains bounded by current Amesp route availability and resource limits"
                )
        return ". ".join(limitation_bits) + "."

    def _plan_steps_text(self, plan: MicroscopicExecutionPlan) -> str:
        return " ".join(f"[{step.step_id}] {step.description}" for step in plan.steps)

    def _successful_result_summary(self, structured_results: dict[str, Any]) -> str:
        route = structured_results.get("attempted_route") or "baseline_bundle"
        executed_capability = structured_results.get("executed_capability") or "run_baseline_bundle"
        route_summary = structured_results.get("route_summary") or {}
        if executed_capability in {
            "run_targeted_charge_analysis",
            "run_targeted_localized_orbital_analysis",
            "run_targeted_natural_orbital_analysis",
            "run_targeted_density_population_analysis",
            "run_targeted_transition_dipole_analysis",
            "run_ris_state_characterization",
            "run_targeted_state_characterization",
        }:
            parsed_records = structured_results.get("parsed_snapshot_records") or structured_results.get("route_records") or []
            summary_label = {
                "run_targeted_charge_analysis": "charge-analysis records",
                "run_targeted_localized_orbital_analysis": "localized-orbital analysis records",
                "run_targeted_natural_orbital_analysis": "natural-orbital analysis records",
                "run_targeted_density_population_analysis": "density/population analysis records",
                "run_targeted_transition_dipole_analysis": "transition-dipole analysis records",
                "run_ris_state_characterization": "RIS state-characterization records",
                "run_targeted_state_characterization": "state-characterization records",
            }[executed_capability]
            return (
                f"Amesp capability '{executed_capability}' reused one existing artifact bundle, ran bounded fixed-geometry "
                f"follow-up calculations for {len(parsed_records)} selected target geometries, and returned {summary_label}. "
                f"Route summary={route_summary}."
            )
        if executed_capability in {
            "parse_snapshot_outputs",
            "extract_ct_descriptors_from_bundle",
            "extract_geometry_descriptors_from_bundle",
            "inspect_raw_artifact_bundle",
        }:
            parsed_records = structured_results.get("parsed_snapshot_records") or structured_results.get("route_records") or []
            bundle_status = (
                route_summary.get("source_bundle_completion_status")
                if isinstance(route_summary, dict)
                else None
            )
            bundle_note = (
                " Source artifact bundle was partial, so returned observables may reflect incomplete snapshot coverage."
                if bundle_status == "partial"
                else ""
            )
            return (
                f"Amesp capability '{executed_capability}' reused existing microscopic artifacts and returned "
                f"{len(parsed_records)} parsed artifact records without new calculations.{bundle_note} "
                f"Route summary={route_summary}."
            )
        s0 = structured_results["s0"]
        s1 = structured_results["s1"]
        manifold = structured_results.get("vertical_state_manifold") or {}
        return (
            f"Amesp route '{route}' finished with final_energy_hartree={s0['final_energy_hartree']}, "
            f"homo_lumo_gap_ev={s0['homo_lumo_gap_ev']}, "
            f"rmsd_from_prepared_structure_angstrom={s0['rmsd_from_prepared_structure_angstrom']}, "
            f"and {len(s0['mulliken_charges'])} Mulliken charges. "
            f"Bounded S1 vertical excitation returned first_excitation_energy_ev={s1['first_excitation_energy_ev']} "
            f"and first_oscillator_strength={s1['first_oscillator_strength']} across {s1['state_count']} states. "
            f"First bright state energy={manifold.get('first_bright_state_energy_ev')} "
            f"with pattern={manifold.get('lowest_state_to_brightest_pattern')}. "
            f"Route summary={route_summary}."
        )

    def _failed_result_summary(self, exc: AmespExecutionError) -> str:
        return f"Amesp microscopic execution returned status={exc.status} with {exc.code}: {exc.message}"

    def _task_completion_for_result(
        self,
        *,
        run_status: str,
        unsupported_requests: list[str],
        task_mode: str,
        capability_route: MicroscopicCapabilityRoute,
        requested_capability: str,
        executed_capability: Optional[str],
        performed_new_calculations: bool,
        reused_existing_artifacts: bool,
        resolved_target_ids: dict[str, Any],
        honored_constraints: list[str],
        unmet_constraints: list[str],
        missing_deliverables: list[str],
        error_message: Optional[str],
        error_payload: Optional[dict[str, Any]],
    ) -> tuple[str, Optional[MicroscopicCompletionReasonCode], str]:
        executed_capability = executed_capability or requested_capability
        action_clause = (
            f"I executed `{executed_capability}`, performed {'new calculations' if performed_new_calculations else 'no new calculations'}, "
            f"and {'reused existing artifacts' if reused_existing_artifacts else 'did not rely on existing artifacts only'}."
        )
        target_clause = (
            f" Resolved targets: {self._resolved_target_ids_text(resolved_target_ids)}."
            if resolved_target_ids
            else ""
        )
        honored_clause = (
            " Honored constraints: " + "; ".join(honored_constraints) + "."
            if honored_constraints
            else ""
        )
        unmet_clause = (
            " Unmet constraints: " + "; ".join(unmet_constraints) + "."
            if unmet_constraints
            else ""
        )
        if run_status == "failed":
            reason_code = self._map_error_to_completion_reason(error_payload)
            return (
                "failed",
                reason_code,
                (
                    f"The Planner requested `{requested_capability}`. {action_clause}{target_clause}{honored_clause}{unmet_clause} "
                    f"The task failed while using Amesp route '{capability_route}': "
                    f"{error_message or 'no error details were provided.'}"
                ),
            )
        if run_status == "partial":
            reason_code = self._map_error_to_completion_reason(error_payload) or "partial_observable_only"
            return (
                "partial",
                reason_code,
                (
                    f"The Planner requested `{requested_capability}`. {action_clause}{target_clause}{honored_clause}{unmet_clause} "
                    f"The task was only partially completed because Amesp route '{capability_route}' was incomplete: "
                    f"{error_message or 'no partial-execution details were provided.'}"
                ),
            )
        if requested_capability != executed_capability or missing_deliverables or unmet_constraints:
            missing_note = (
                " Missing deliverables: " + "; ".join(missing_deliverables) + "."
                if missing_deliverables
                else ""
            )
            unsupported_note = (
                " Unsupported background requests were also noted: " + "; ".join(unsupported_requests) + "."
                if unsupported_requests
                else ""
            )
            return (
                "contracted",
                "partial_observable_only",
                (
                    f"The Planner requested `{requested_capability}`. {action_clause}{target_clause}{honored_clause}{unmet_clause} "
                    f"The task completed in a contracted form via Amesp route '{capability_route}'.{missing_note}"
                    f"{unsupported_note}"
                ),
            )
        if unsupported_requests:
            unsupported = "; ".join(unsupported_requests)
            if capability_route == "excited_state_relaxation_follow_up":
                return (
                    "contracted",
                    "capability_unsupported",
                    f"The Planner requested `{requested_capability}`. {action_clause}{target_clause}{honored_clause}{unmet_clause} "
                    "The requested excited-state relaxation follow-up is not yet validated "
                    f"within current Amesp capability, so route '{capability_route}' could not be executed. "
                    f"Unsupported parts were: {unsupported}.",
                )
            if task_mode == "targeted_follow_up":
                return (
                    "contracted",
                    "partial_observable_only",
                    f"The Planner requested `{requested_capability}`. {action_clause}{target_clause}{honored_clause}{unmet_clause} "
                    f"The requested targeted microscopic follow-up could not be executed exactly as asked, so Amesp route "
                    f"'{capability_route}' returned the closest bounded substitute instead. "
                    f"Unsupported parts were: {unsupported}.",
                )
            return (
                "contracted",
                "partial_observable_only",
                f"The Planner requested `{requested_capability}`. {action_clause}{target_clause}{honored_clause}{unmet_clause} "
                    f"The agent returned bounded Amesp route '{capability_route}' evidence, but it could not execute unsupported "
                    f"parts of the Planner instruction: {unsupported}.",
                )
        return (
            "completed",
            None,
            (
                f"The Planner requested `{requested_capability}`. {action_clause}{target_clause}{honored_clause}{unmet_clause} "
                "All requested deliverables were produced within current microscopic capability."
                + (
                    " Unsupported background requests were noted but did not block the executed capability: "
                    + "; ".join(unsupported_requests)
                    + "."
                    if unsupported_requests
                    else ""
                )
            ),
        )

    def _missing_deliverables_text(self, missing_deliverables: list[str]) -> str:
        if not missing_deliverables:
            return "No requested deliverables were missing."
        return "; ".join(missing_deliverables)

    def _resolved_target_ids_text(self, resolved_target_ids: dict[str, Any]) -> str:
        if not resolved_target_ids:
            return "No resolved target IDs were recorded."
        parts: list[str] = []
        for key in sorted(resolved_target_ids):
            parts.append(f"{key}={resolved_target_ids[key]}")
        return "; ".join(parts)

    def _constraint_text(self, constraints: list[str], *, default_text: str) -> str:
        if not constraints:
            return default_text
        return "; ".join(constraints)

    def _vertical_state_manifold(self, s1_result: Any) -> dict[str, Any]:
        excited_states = list(getattr(s1_result, "excited_states", []))
        bright_states = [state for state in excited_states if getattr(state, "oscillator_strength", 0.0) > 0.05]
        first_bright = bright_states[0] if bright_states else None
        return {
            "state_count": getattr(s1_result, "state_count", len(excited_states)),
            "first_bright_state_energy_ev": (
                getattr(first_bright, "excitation_energy_ev", None) if first_bright is not None else None
            ),
            "first_bright_state_oscillator_strength": (
                getattr(first_bright, "oscillator_strength", None) if first_bright is not None else None
            ),
            "lowest_state_to_brightest_pattern": (
                "lowest_state_is_bright"
                if first_bright is not None and getattr(first_bright, "state_index", None) == 1
                else "lowest_state_is_dark_then_bright"
                if first_bright is not None
                else "no_bright_state_detected"
            ),
            "oscillator_strength_summary": {
                "sum": round(sum(getattr(state, "oscillator_strength", 0.0) for state in excited_states), 6),
                "max": max((getattr(state, "oscillator_strength", 0.0) for state in excited_states), default=None),
            },
        }

    def _map_error_to_completion_reason(
        self,
        error_payload: Optional[dict[str, Any]],
    ) -> Optional[MicroscopicCompletionReasonCode]:
        if not error_payload:
            return None
        code = error_payload.get("code")
        if code in {"capability_unsupported"}:
            return "capability_unsupported"
        if code in {"precondition_missing", "structure_unavailable", "shared_structure_unavailable"}:
            return "precondition_missing"
        if code in {"resource_budget_exceeded"}:
            return "resource_budget_exceeded"
        if code in {"parse_failed"}:
            return "parse_failed"
        if code in {"action_not_supported_by_registry"}:
            return "action_not_supported_by_registry"
        if code in {"protocol_parse_failed"}:
            return "protocol_parse_failed"
        if code in {"subprocess_failed", "normal_termination_missing", "amesp_binary_missing"}:
            return "runtime_failed"
        return None
