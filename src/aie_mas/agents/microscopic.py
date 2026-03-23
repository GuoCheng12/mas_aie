from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Literal, Optional, Protocol

from pydantic import BaseModel, Field

from aie_mas.compat.langchain import prompt_value_to_messages
from aie_mas.config import AieMasConfig
from aie_mas.graph.state import (
    AgentReport,
    MicroscopicExecutionPlan,
    MicroscopicExecutionStep,
    MicroscopicTaskSpec,
    WorkflowProgressEvent,
)
from aie_mas.llm.openai_compatible import OpenAICompatibleMicroscopicClient
from aie_mas.tools.amesp import AmespBaselineMicroscopicTool, AmespExecutionError
from aie_mas.tools.microscopic import (
    MockS0OptimizationTool,
    MockS1OptimizationTool,
    MockTargetedMicroscopicTool,
)
from aie_mas.utils.prompts import PromptRepository


MicroscopicStructureStrategy = Literal[
    "prepare_from_smiles",
    "reuse_if_available_else_prepare_from_smiles",
]


def _default_prompt_repository() -> PromptRepository:
    return PromptRepository(Path(__file__).resolve().parents[1] / "prompts")


class MicroscopicReasoningPlanDraft(BaseModel):
    local_goal: str
    requested_deliverables: list[str] = Field(default_factory=list)
    structure_strategy: MicroscopicStructureStrategy = "reuse_if_available_else_prepare_from_smiles"
    step_sequence: list[Literal["structure_prep", "s0_optimization", "s1_vertical_excitation"]] = Field(
        default_factory=lambda: ["structure_prep", "s0_optimization", "s1_vertical_excitation"]
    )
    unsupported_requests: list[str] = Field(default_factory=list)


class MicroscopicReasoningResponse(BaseModel):
    task_understanding: str
    reasoning_summary: str
    execution_plan: MicroscopicReasoningPlanDraft
    capability_limit_note: str
    expected_outputs: list[str] = Field(default_factory=list)
    failure_policy: str


class MicroscopicReasoningBackend(Protocol):
    def reason(self, rendered_prompt: Any, payload: dict[str, Any]) -> MicroscopicReasoningResponse:
        ...


class MockMicroscopicReasoningBackend:
    def reason(self, rendered_prompt: Any, payload: dict[str, Any]) -> MicroscopicReasoningResponse:
        _ = rendered_prompt
        task_instruction = str(payload["task_instruction"])
        requested_deliverables = list(payload["requested_deliverables"])
        unsupported_requests = list(payload["unsupported_requests"])
        structure_context = payload["available_structure_context"]
        task_mode = payload["task_mode"]
        recent_rounds_context = payload["recent_rounds_context"]

        if structure_context.get("has_prepared_structure"):
            structure_strategy: MicroscopicStructureStrategy = "reuse_if_available_else_prepare_from_smiles"
            structure_note = "A prepared 3D structure is already available and should be reused if possible."
        else:
            structure_strategy = "prepare_from_smiles"
            structure_note = "No prepared 3D structure is available, so the run must start from SMILES-to-3D preparation."

        recent_note = (
            f"Recent microscopic context includes {len(recent_rounds_context)} prior round(s)."
            if recent_rounds_context
            else "No prior microscopic round context is available."
        )
        capability_limit_note = (
            "Current microscopic capability is bounded to a low-cost Amesp baseline only: structure preparation or "
            "reuse, low-cost S0 optimization, and bounded S1 vertical excitation. No global mechanism judgment is allowed."
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

        expected_outputs = [
            "Low-cost S0 optimized geometry",
            "Low-cost S0 final energy",
            "S0 dipole",
            "S0 Mulliken charges",
            "S0 HOMO-LUMO gap",
            "S1 first excitation energy",
            "S1 first oscillator strength",
        ]
        reasoning_summary = (
            f"Interpret the Planner instruction as a bounded Amesp baseline task. {structure_note} "
            f"{recent_note} Requested local deliverables: {', '.join(requested_deliverables)}. "
            f"{capability_limit_note}"
        )
        return MicroscopicReasoningResponse(
            task_understanding=(
                f"Use the Planner instruction to collect local microscopic evidence for the current working hypothesis "
                f"'{payload['current_hypothesis']}' without making any global mechanism judgment: {task_instruction}"
            ),
            reasoning_summary=reasoning_summary,
            execution_plan=MicroscopicReasoningPlanDraft(
                local_goal=(
                "Collect bounded low-cost microscopic evidence through the Amesp baseline workflow and return only local results."
            ),
                requested_deliverables=requested_deliverables,
                structure_strategy=structure_strategy,
                step_sequence=["structure_prep", "s0_optimization", "s1_vertical_excitation"],
                unsupported_requests=unsupported_requests,
            ),
            capability_limit_note=capability_limit_note,
            expected_outputs=expected_outputs,
            failure_policy=(
                "If any Amesp step fails, return a local failed or partial report with the available artifacts and "
                "do not escalate into a global mechanism decision."
            ),
        )


class OpenAIMicroscopicReasoningBackend:
    def __init__(
        self,
        config: AieMasConfig,
        client: Optional[OpenAICompatibleMicroscopicClient] = None,
    ) -> None:
        self._client = client or OpenAICompatibleMicroscopicClient(config)

    def reason(self, rendered_prompt: Any, payload: dict[str, Any]) -> MicroscopicReasoningResponse:
        _ = payload
        response = self._client.invoke_json_schema(
            messages=prompt_value_to_messages(rendered_prompt),
            response_model=MicroscopicReasoningResponse,
            schema_name="microscopic_reasoning_response",
        )
        return MicroscopicReasoningResponse.model_validate(response.model_dump(mode="json"))


class MicroscopicAgent:
    def __init__(
        self,
        s0_tool: Optional[MockS0OptimizationTool] = None,
        s1_tool: Optional[MockS1OptimizationTool] = None,
        targeted_tool: Optional[MockTargetedMicroscopicTool] = None,
        *,
        amesp_tool: Optional[AmespBaselineMicroscopicTool] = None,
        prompts: Optional[PromptRepository] = None,
        tools_work_dir: Optional[Path] = None,
        config: Optional[AieMasConfig] = None,
        llm_client: Optional[OpenAICompatibleMicroscopicClient] = None,
        progress_callback: Optional[Callable[[WorkflowProgressEvent], None]] = None,
    ) -> None:
        self._s0_tool = s0_tool or MockS0OptimizationTool()
        self._s1_tool = s1_tool or MockS1OptimizationTool()
        self._targeted_tool = targeted_tool or MockTargetedMicroscopicTool()
        self._amesp_tool = amesp_tool
        self._prompts = prompts or _default_prompt_repository()
        self._tools_work_dir = tools_work_dir
        self._config = config or AieMasConfig()
        self._reasoning_backend = self._build_reasoning_backend(self._config, llm_client)
        self._progress_callback = progress_callback

    def run(
        self,
        smiles: str,
        task_received: str,
        task_spec: Optional[MicroscopicTaskSpec] = None,
        current_hypothesis: str = "unknown",
        *,
        recent_rounds_context: Optional[list[dict[str, object]]] = None,
        available_artifacts: Optional[dict[str, Any]] = None,
        case_id: Optional[str] = None,
        round_index: int = 1,
    ) -> AgentReport:
        task_spec = task_spec or MicroscopicTaskSpec(
            mode="baseline_s0_s1",
            task_label="initial-baseline",
            objective="Run fixed first-stage S0/S1 optimization.",
        )
        recent_rounds_context = recent_rounds_context or []
        available_artifacts = available_artifacts or {}
        resolved_case_id = case_id or "ad_hoc_case"

        self._emit_probe(
            round_index=round_index,
            case_id=resolved_case_id,
            current_hypothesis=current_hypothesis,
            stage="reasoning",
            status="start",
            details={
                "task_instruction": task_received,
                "task_mode": task_spec.mode,
                "task_label": task_spec.task_label,
            },
        )

        reasoning_payload = self._build_reasoning_payload(
            current_hypothesis=current_hypothesis,
            task_instruction=task_received,
            task_spec=task_spec,
            recent_rounds_context=recent_rounds_context,
            available_artifacts=available_artifacts,
        )
        rendered_prompt = self._prompts.render("microscopic_reasoning", reasoning_payload)
        reasoning = self._reasoning_backend.reason(rendered_prompt, reasoning_payload)
        self._emit_probe(
            round_index=round_index,
            case_id=resolved_case_id,
            current_hypothesis=current_hypothesis,
            stage="reasoning",
            status="end",
            details={
                "reasoning_backend": self._config.microscopic_backend,
                "task_understanding": reasoning.task_understanding,
                "reasoning_summary": reasoning.reasoning_summary,
                "capability_limit_note": reasoning.capability_limit_note,
                "expected_outputs": reasoning.expected_outputs,
            },
        )
        plan = self._normalize_execution_plan(
            task_received=task_received,
            task_spec=task_spec,
            available_artifacts=available_artifacts,
            reasoning=reasoning,
        )
        self._emit_probe(
            round_index=round_index,
            case_id=resolved_case_id,
            current_hypothesis=current_hypothesis,
            stage="execution_plan",
            status="end",
            details=plan.model_dump(mode="json"),
        )

        if self._amesp_tool is not None:
            return self._run_real(
                smiles=smiles,
                task_received=task_received,
                task_spec=task_spec,
                current_hypothesis=current_hypothesis,
                reasoning=reasoning,
                plan=plan,
                recent_rounds_context=recent_rounds_context,
                available_artifacts=available_artifacts,
                case_id=resolved_case_id,
                round_index=round_index,
            )
        return self._run_mock(
            smiles=smiles,
            task_received=task_received,
            task_spec=task_spec,
            current_hypothesis=current_hypothesis,
            reasoning=reasoning,
            plan=plan,
        )

    def _run_real(
        self,
        *,
        smiles: str,
        task_received: str,
        task_spec: MicroscopicTaskSpec,
        current_hypothesis: str,
        reasoning: MicroscopicReasoningResponse,
        plan: MicroscopicExecutionPlan,
        recent_rounds_context: list[dict[str, object]],
        available_artifacts: dict[str, Any],
        case_id: str,
        round_index: int,
    ) -> AgentReport:
        render_payload = {
            "task_received": task_received,
            "current_hypothesis": current_hypothesis,
            "requested_focus": ", ".join(plan.requested_deliverables),
            "recent_context_note": self._recent_context_note(recent_rounds_context),
            "capability_scope": self._capability_scope_text(),
            "structure_source_note": self._structure_source_note(plan.structure_source, available_artifacts),
            "unsupported_requests_note": self._unsupported_requests_note(plan.unsupported_requests),
            "reasoning_summary_text": reasoning.reasoning_summary,
            "capability_limit_note": reasoning.capability_limit_note,
            "failure_policy": reasoning.failure_policy,
            "plan_steps": self._plan_steps_text(plan),
            "expected_outputs_text": ", ".join(plan.expected_outputs),
            "result_summary_text": "Amesp baseline execution has not run yet.",
            "local_uncertainty_detail": self._remaining_uncertainty_text(
                plan.unsupported_requests,
                task_spec.mode,
            ),
        }
        draft = self._prompts.render_sections("microscopic_amesp_specialized", render_payload)

        label = f"{case_id}_round_{round_index:02d}_micro"
        workdir = self._resolve_workdir(case_id=case_id, round_index=round_index)
        tool_calls = [
            "microscopic_reasoning(task_instruction_to_execution_plan)",
            "structure_preparation(smiles_to_3d or reusable prepared structure)",
            f"{self._amesp_tool.name}.execute(plan_version='{plan.plan_version}', label='{label}')",
        ]

        try:
            run_result = self._amesp_tool.execute(
                plan=plan,
                smiles=smiles,
                label=label,
                workdir=workdir,
                available_artifacts=available_artifacts,
                progress_callback=self._progress_callback,
                round_index=round_index,
                case_id=case_id,
                current_hypothesis=current_hypothesis,
            )
            structured_results = {
                "backend": "amesp",
                "reasoning_backend": self._config.microscopic_backend,
                "task_mode": task_spec.mode,
                "task_label": task_spec.task_label,
                "task_objective": task_spec.objective,
                "reasoning": reasoning.model_dump(mode="json"),
                "execution_plan": plan.model_dump(mode="json"),
                "structure_source": plan.structure_source,
                "supported_scope": plan.supported_scope,
                "unsupported_requests": plan.unsupported_requests,
                "structure": run_result.structure.model_dump(mode="json"),
                "s0": run_result.s0.model_dump(mode="json"),
                "s1": run_result.s1.model_dump(mode="json"),
                "s0_energy": run_result.s0.final_energy_hartree,
                "s1_energy": (
                    run_result.s1.excited_states[0].total_energy_hartree
                    if run_result.s1.excited_states
                    else None
                ),
                "rigidity_proxy": None,
                "geometry_change_proxy": getattr(
                    run_result.s0,
                    "rmsd_from_prepared_structure_angstrom",
                    None,
                ),
                "oscillator_strength_proxy": getattr(run_result.s1, "first_oscillator_strength", None),
                "relaxation_gap": getattr(run_result.s1, "first_excitation_energy_ev", None),
            }
            raw_results = {
                "reasoning_output": reasoning.model_dump(mode="json"),
                "execution_plan": plan.model_dump(mode="json"),
                "amesp_raw_step_results": run_result.raw_step_results,
            }
            generated_artifacts = dict(run_result.generated_artifacts)
            result_summary_text = self._successful_result_summary(structured_results)
            status = "success"
        except AmespExecutionError as exc:
            structured_results = {
                "backend": "amesp",
                "reasoning_backend": self._config.microscopic_backend,
                "task_mode": task_spec.mode,
                "task_label": task_spec.task_label,
                "task_objective": task_spec.objective,
                "reasoning": reasoning.model_dump(mode="json"),
                "execution_plan": plan.model_dump(mode="json"),
                "structure_source": plan.structure_source,
                "supported_scope": plan.supported_scope,
                "unsupported_requests": plan.unsupported_requests,
                "error": exc.to_payload(),
                **exc.structured_results,
            }
            raw_results = {
                "reasoning_output": reasoning.model_dump(mode="json"),
                "execution_plan": plan.model_dump(mode="json"),
                "amesp_error": exc.to_payload(),
                **exc.raw_results,
            }
            generated_artifacts = dict(exc.generated_artifacts)
            result_summary_text = self._failed_result_summary(exc)
            status = exc.status

        rendered = self._prompts.render_sections(
            "microscopic_amesp_specialized",
            {
                **render_payload,
                "result_summary_text": result_summary_text,
            },
        )

        return AgentReport(
            agent_name="microscopic",
            task_received=task_received,
            task_understanding=draft["task_understanding"],
            reasoning_summary=rendered["reasoning_summary"],
            execution_plan=rendered["execution_plan"],
            result_summary=rendered["result_summary"],
            remaining_local_uncertainty=rendered["remaining_local_uncertainty"],
            tool_calls=tool_calls,
            raw_results=raw_results,
            structured_results=structured_results,
            generated_artifacts=generated_artifacts,
            status=status,  # type: ignore[arg-type]
            planner_readable_report=rendered["planner_readable_report"],
        )

    def _run_mock(
        self,
        *,
        smiles: str,
        task_received: str,
        task_spec: MicroscopicTaskSpec,
        current_hypothesis: str,
        reasoning: MicroscopicReasoningResponse,
        plan: MicroscopicExecutionPlan,
    ) -> AgentReport:
        render_payload = {
            "task_received": task_received,
            "current_hypothesis": current_hypothesis,
            "task_mode": task_spec.mode,
            "reasoning_summary_text": reasoning.reasoning_summary,
            "execution_plan_text": self._plan_steps_text(plan),
            "targeted_summary": self._targeted_summary_text(None),
            "local_uncertainty_detail": self._micro_uncertainty_text(task_spec, reasoning.capability_limit_note),
            "s0_energy": "pending",
            "s1_energy": "pending",
            "rigidity_proxy": "pending",
            "geometry_change_proxy": "pending",
            "oscillator_strength_proxy": "pending",
            "relaxation_gap": "pending",
        }
        draft = self._prompts.render_sections("microscopic_specialized", render_payload)

        s0_result = self._s0_tool.invoke(smiles)
        s1_result = self._s1_tool.invoke(smiles)
        relaxation_gap = round(abs(s1_result["optimized_energy"] - s0_result["optimized_energy"]), 4)
        structured_results = {
            "reasoning_backend": self._config.microscopic_backend,
            "reasoning": reasoning.model_dump(mode="json"),
            "execution_plan": plan.model_dump(mode="json"),
            "task_mode": task_spec.mode,
            "task_label": task_spec.task_label,
            "task_objective": task_spec.objective,
            "target_property": task_spec.target_property,
            "s0_energy": s0_result["optimized_energy"],
            "s1_energy": s1_result["optimized_energy"],
            "rigidity_proxy": s0_result["rigidity_proxy"],
            "geometry_change_proxy": s1_result["geometry_change_proxy"],
            "oscillator_strength_proxy": s1_result["oscillator_strength_proxy"],
            "relaxation_gap": relaxation_gap,
        }
        tool_calls = [
            "microscopic_reasoning(task_instruction_to_execution_plan)",
            f"{self._s0_tool.name}(smiles='{smiles}')",
            f"{self._s1_tool.name}(smiles='{smiles}')",
        ]
        raw_results = {
            "reasoning_output": reasoning.model_dump(mode="json"),
            "s0_optimization": s0_result,
            "s1_optimization": s1_result,
        }

        targeted_result: Optional[dict[str, Any]] = None
        if task_spec.mode == "targeted_follow_up":
            targeted_result = self._targeted_tool.invoke(
                smiles,
                objective=task_spec.objective,
                target_property=task_spec.target_property,
            )
            structured_results["targeted_follow_up"] = targeted_result
            raw_results["targeted_follow_up"] = targeted_result
            tool_calls.append(
                f"{self._targeted_tool.name}(smiles='{smiles}', objective='{task_spec.objective}')"
            )

        rendered = self._prompts.render_sections(
            "microscopic_specialized",
            {
                **render_payload,
                "targeted_summary": self._targeted_summary_text(targeted_result),
                "s0_energy": structured_results["s0_energy"],
                "s1_energy": structured_results["s1_energy"],
                "rigidity_proxy": structured_results["rigidity_proxy"],
                "geometry_change_proxy": structured_results["geometry_change_proxy"],
                "oscillator_strength_proxy": structured_results["oscillator_strength_proxy"],
                "relaxation_gap": structured_results["relaxation_gap"],
            },
        )

        return AgentReport(
            agent_name="microscopic",
            task_received=task_received,
            task_understanding=draft["task_understanding"],
            reasoning_summary=rendered["reasoning_summary"],
            execution_plan=rendered["execution_plan"],
            result_summary=rendered["result_summary"],
            remaining_local_uncertainty=rendered["remaining_local_uncertainty"],
            tool_calls=tool_calls,
            raw_results=raw_results,
            structured_results=structured_results,
            generated_artifacts={},
            status="success",
            planner_readable_report=rendered["planner_readable_report"],
        )

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
        if config.microscopic_backend == "openai_sdk":
            return OpenAIMicroscopicReasoningBackend(config, client=llm_client)
        return MockMicroscopicReasoningBackend()

    def _build_reasoning_payload(
        self,
        *,
        current_hypothesis: str,
        task_instruction: str,
        task_spec: MicroscopicTaskSpec,
        recent_rounds_context: list[dict[str, object]],
        available_artifacts: dict[str, Any],
    ) -> dict[str, Any]:
        requested_deliverables = self._requested_deliverables(task_instruction)
        unsupported_requests = self._unsupported_requests(task_instruction, task_spec)
        return {
            "current_hypothesis": current_hypothesis,
            "task_instruction": task_instruction,
            "task_mode": task_spec.mode,
            "requested_deliverables": requested_deliverables,
            "unsupported_requests": unsupported_requests,
            "recent_rounds_context": recent_rounds_context,
            "available_structure_context": self._available_structure_context(available_artifacts),
            "runtime_context": self._runtime_context_summary(),
        }

    def _normalize_execution_plan(
        self,
        *,
        task_received: str,
        task_spec: MicroscopicTaskSpec,
        available_artifacts: dict[str, Any],
        reasoning: MicroscopicReasoningResponse,
    ) -> MicroscopicExecutionPlan:
        requested_deliverables = (
            list(reasoning.execution_plan.requested_deliverables)
            if reasoning.execution_plan.requested_deliverables
            else self._requested_deliverables(task_received)
        )
        unsupported_requests = list(reasoning.execution_plan.unsupported_requests)
        structure_source = (
            "existing_prepared_structure"
            if reasoning.execution_plan.structure_strategy == "reuse_if_available_else_prepare_from_smiles"
            and self._has_reusable_structure(available_artifacts)
            else "prepared_from_smiles"
        )
        step_sequence = list(reasoning.execution_plan.step_sequence) or [
            "structure_prep",
            "s0_optimization",
            "s1_vertical_excitation",
        ]
        steps = [self._build_step(step_type, structure_source) for step_type in step_sequence]
        expected_outputs = list(reasoning.expected_outputs) or [
            "S0 optimized geometry",
            "S0 final energy",
            "S0 dipole",
            "S0 Mulliken charges",
            "S0 HOMO-LUMO gap",
            "S1 first excitation energy",
            "S1 first oscillator strength",
        ]
        if task_spec.mode == "targeted_follow_up":
            targeted_note = "targeted microscopic follow-up beyond the current Amesp baseline workflow"
            if targeted_note not in unsupported_requests:
                unsupported_requests.append(targeted_note)
        return MicroscopicExecutionPlan(
            local_goal=reasoning.execution_plan.local_goal,
            requested_deliverables=requested_deliverables,
            structure_source=structure_source,  # type: ignore[arg-type]
            supported_scope=[
                "low-cost aTB S0 geometry optimization",
                "Mulliken charge extraction",
                "dipole extraction",
                "HOMO-LUMO gap extraction",
                "S1 vertical excitation energies",
                "S1 oscillator strength extraction",
            ],
            unsupported_requests=unsupported_requests,
            steps=steps,
            expected_outputs=expected_outputs,
            failure_reporting=reasoning.failure_policy,
        )

    def _build_step(
        self,
        step_type: Literal["structure_prep", "s0_optimization", "s1_vertical_excitation"],
        structure_source: str,
    ) -> MicroscopicExecutionStep:
        if step_type == "structure_prep":
            return MicroscopicExecutionStep(
                step_id="structure_prep",
                step_type="structure_prep",
                description=(
                    "Reuse a prepared 3D structure if available; otherwise generate a 3D structure from the input SMILES."
                ),
                input_source="available prepared structure artifacts or SMILES",
                expected_outputs=[
                    "prepared_structure.xyz",
                    "prepared_structure.sdf",
                    "structure_prep_summary.json",
                ],
            )
        if step_type == "s0_optimization":
            return MicroscopicExecutionStep(
                step_id="s0_optimization",
                step_type="s0_optimization",
                description="Run a real low-cost Amesp aTB S0 geometry optimization on the prepared 3D structure.",
                input_source=structure_source,
                keywords=["atb", "opt", "force", "maxcyc 2000", "gediis off", "maxstep 0.3", "vshift 500"],
                expected_outputs=[
                    "low-cost final S0 energy",
                    "low-cost final geometry",
                    "dipole",
                    "Mulliken charges",
                    "HOMO-LUMO gap",
                ],
            )
        return MicroscopicExecutionStep(
            step_id="s1_vertical_excitation",
            step_type="s1_vertical_excitation",
            description=(
                "Run a bounded real Amesp S1 vertical excitation calculation at the best available S0 geometry "
                "to characterize the first singlet excited-state manifold without escalating to heavy excited-state optimization."
            ),
            input_source="S0 optimized geometry",
            keywords=[
                "b3lyp",
                "sto-3g",
                "td",
                f"nstates {self._config.amesp_s1_nstates}",
                f"tout {self._config.amesp_td_tout}",
            ],
            expected_outputs=["excited-state energies", "oscillator strengths"],
        )

    def _available_structure_context(self, available_artifacts: dict[str, Any]) -> dict[str, Any]:
        context = {
            "has_prepared_structure": False,
            "prepared_xyz_path": None,
            "prepared_summary_path": None,
            "prepared_atom_count": None,
            "prepared_charge": None,
            "prepared_multiplicity": None,
        }
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
        return context

    def _runtime_context_summary(self) -> dict[str, Any]:
        return {
            "microscopic_backend": self._config.microscopic_backend,
            "tool_backend": self._config.tool_backend,
            "amesp_binary_path": str(self._config.amesp_binary_path) if self._config.amesp_binary_path else None,
            "supports_real_amesp": self._amesp_tool is not None,
            "baseline_policy": (
                "baseline-first must stay low-cost; do not default to heavy exhaustive DFT geometry optimization for large systems"
            ),
            "supported_scope": [
                "structure preparation or reuse",
                "low-cost aTB S0 optimization",
                "bounded S1 vertical excitation",
            ],
            "unsupported_scope": [
                "heavy full-DFT geometry optimization as a default first-round baseline",
                "excited-state optimization",
                "scan",
                "TS",
                "IRC",
                "solvent",
                "SOC",
                "NAC",
                "AIMD",
            ],
        }

    def _resolve_workdir(self, *, case_id: str, round_index: int) -> Path:
        base_dir = self._tools_work_dir or (Path.cwd() / "var" / "runtime" / "tools")
        return base_dir / "microscopic" / case_id / f"round_{round_index:02d}"

    def _requested_deliverables(self, task_received: str) -> list[str]:
        lower_instruction = task_received.lower()
        deliverables: list[str] = []
        if any(token in lower_instruction for token in ("s0", "ground-state", "ground state", "opt")):
            deliverables.append("low-cost aTB S0 geometry optimization")
        if any(token in lower_instruction for token in ("s1", "excited", "oscillator", "vertical")):
            deliverables.append("S1 vertical excitation characterization")
        if "dipole" in lower_instruction:
            deliverables.append("dipole summary")
        if "charge" in lower_instruction:
            deliverables.append("Mulliken charge summary")
        if not deliverables:
            deliverables.extend(
                [
                    "low-cost aTB S0 geometry optimization",
                    "S1 vertical excitation characterization",
                ]
            )
        return deliverables

    def _unsupported_requests(
        self,
        task_received: str,
        task_spec: MicroscopicTaskSpec,
    ) -> list[str]:
        lower_instruction = task_received.lower()
        unsupported: list[str] = []
        keyword_mapping = {
            "torsion scan": ("scan", "torsion"),
            "heavy full-DFT geometry optimization": ("full dft", "exhaustive geometry optimization"),
            "transition-state optimization": ("transition state", "ts"),
            "IRC": ("irc",),
            "solvent model": ("solvent", "cpcm", "cosmo"),
            "SOC/NAC analysis": ("soc", "nac"),
            "AIMD": ("aimd", "dynamics"),
            "bond-order analysis": ("bond order", "mayer"),
        }
        for label, tokens in keyword_mapping.items():
            if any(token in lower_instruction for token in tokens):
                unsupported.append(label)
        if task_spec.mode == "targeted_follow_up":
            unsupported.append("targeted microscopic follow-up beyond the current Amesp baseline workflow")
        return unsupported

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
            "Current microscopic capability is limited to a real low-cost Amesp baseline workflow: aTB S0 geometry "
            "optimization plus bounded S1 vertical excitation analysis."
        )

    def _structure_source_note(
        self,
        structure_source: str,
        available_artifacts: dict[str, Any],
    ) -> str:
        if structure_source == "existing_prepared_structure":
            return "Reuse the previously prepared 3D structure artifacts that are already available for this case."
        if available_artifacts.get("prepared_xyz_path"):
            return (
                "A previous prepared structure was referenced but is not reusable from disk, so a fresh 3D structure "
                "will be generated from the input SMILES before the low-cost baseline run."
            )
        return "Prepare a fresh 3D structure from the input SMILES before running the low-cost Amesp baseline."

    def _unsupported_requests_note(self, unsupported_requests: list[str]) -> str:
        if not unsupported_requests:
            return "No unsupported local request was detected."
        return "; ".join(unsupported_requests)

    def _remaining_uncertainty_text(
        self,
        unsupported_requests: list[str],
        task_mode: str,
    ) -> str:
        limitation_bits = [
            "this bounded low-cost Amesp baseline run does not execute excited-state optimization",
            "it does not adjudicate the global mechanism",
        ]
        if unsupported_requests:
            limitation_bits.append(
                "it also leaves unsupported local requests unresolved: " + "; ".join(unsupported_requests)
            )
        if task_mode == "targeted_follow_up":
            limitation_bits.append(
                "the requested targeted microscopic follow-up is conservatively contracted to the same low-cost baseline S0/S1 workflow"
            )
        return ". ".join(limitation_bits) + "."

    def _plan_steps_text(self, plan: MicroscopicExecutionPlan) -> str:
        return " ".join(f"[{step.step_id}] {step.description}" for step in plan.steps)

    def _successful_result_summary(self, structured_results: dict[str, Any]) -> str:
        s0 = structured_results["s0"]
        s1 = structured_results["s1"]
        return (
            f"Low-cost S0 optimization finished with final_energy_hartree={s0['final_energy_hartree']}, "
            f"homo_lumo_gap_ev={s0['homo_lumo_gap_ev']}, "
            f"rmsd_from_prepared_structure_angstrom={s0['rmsd_from_prepared_structure_angstrom']}, "
            f"and {len(s0['mulliken_charges'])} Mulliken charges. "
            f"Bounded S1 vertical excitation returned first_excitation_energy_ev={s1['first_excitation_energy_ev']} "
            f"and first_oscillator_strength={s1['first_oscillator_strength']} across {s1['state_count']} states."
        )

    def _failed_result_summary(self, exc: AmespExecutionError) -> str:
        return f"Amesp baseline execution returned status={exc.status} with {exc.code}: {exc.message}"

    def _targeted_summary_text(self, targeted_result: Optional[dict[str, Any]]) -> str:
        if targeted_result is None:
            return "No targeted follow-up result was produced in this run."
        return (
            "Targeted follow-up recorded "
            f"consistency_proxy={targeted_result['consistency_proxy']} and "
            f"constraint_sensitivity={targeted_result['constraint_sensitivity']}."
        )

    def _micro_uncertainty_text(
        self,
        task_spec: MicroscopicTaskSpec,
        capability_limit_note: str,
    ) -> str:
        if task_spec.mode == "targeted_follow_up":
            return (
                "the targeted micro follow-up still cannot establish verifier-aligned mechanism selection "
                f"without Planner-level synthesis. {capability_limit_note}"
            )
        return f"the bounded low-cost baseline S0/S1 run still cannot determine external consistency or final mechanism. {capability_limit_note}"
