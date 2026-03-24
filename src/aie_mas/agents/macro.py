from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Protocol

from pydantic import BaseModel, Field

from aie_mas.compat.langchain import prompt_value_to_messages
from aie_mas.config import AieMasConfig
from aie_mas.graph.state import (
    AgentReport,
    MacroExecutionPlan,
    MacroExecutionStep,
    SharedStructureContext,
)
from aie_mas.llm.openai_compatible import OpenAICompatibleMacroClient
from aie_mas.tools.macro import DeterministicMacroStructureTool
from aie_mas.utils.prompts import PromptRepository


def _default_prompt_repository() -> PromptRepository:
    return PromptRepository(Path(__file__).resolve().parents[1] / "prompts")


class MacroReasoningPlanDraft(BaseModel):
    local_goal: str
    requested_deliverables: list[str] = Field(default_factory=list)
    focus_areas: list[str] = Field(default_factory=list)
    unsupported_requests: list[str] = Field(default_factory=list)


class MacroReasoningResponse(BaseModel):
    task_understanding: str
    reasoning_summary: str
    execution_plan: MacroReasoningPlanDraft
    capability_limit_note: str
    expected_outputs: list[str] = Field(default_factory=list)
    failure_policy: str


class MacroReasoningBackend(Protocol):
    def reason(self, rendered_prompt: Any, payload: dict[str, Any]) -> MacroReasoningResponse:
        ...


class OpenAIMacroReasoningBackend:
    def __init__(
        self,
        config: AieMasConfig,
        client: Optional[OpenAICompatibleMacroClient] = None,
    ) -> None:
        self._client = client or OpenAICompatibleMacroClient(config)

    def reason(self, rendered_prompt: Any, payload: dict[str, Any]) -> MacroReasoningResponse:
        _ = payload
        response = self._client.invoke_json_schema(
            messages=prompt_value_to_messages(rendered_prompt),
            response_model=MacroReasoningResponse,
            schema_name="macro_reasoning_response",
        )
        return MacroReasoningResponse.model_validate(response.model_dump(mode="json"))


class MacroAgent:
    def __init__(
        self,
        tool: DeterministicMacroStructureTool | None = None,
        prompts: PromptRepository | None = None,
        config: Optional[AieMasConfig] = None,
        llm_client: Optional[OpenAICompatibleMacroClient] = None,
    ) -> None:
        self._tool = tool or DeterministicMacroStructureTool()
        self._prompts = prompts or _default_prompt_repository()
        self._config = config or AieMasConfig()
        self._reasoning_backend = self._build_reasoning_backend(self._config, llm_client)

    def run(
        self,
        smiles: str,
        task_received: str,
        current_hypothesis: str = "unknown",
        *,
        recent_rounds_context: Optional[list[dict[str, object]]] = None,
        shared_structure_context: Optional[SharedStructureContext] = None,
        case_id: Optional[str] = None,
        round_index: int = 1,
    ) -> AgentReport:
        del case_id, round_index
        recent_rounds_context = recent_rounds_context or []
        reasoning_payload = {
            "current_hypothesis": current_hypothesis,
            "task_instruction": task_received,
            "recent_rounds_context": recent_rounds_context,
            "shared_structure_context": (
                shared_structure_context.model_dump(mode="json")
                if shared_structure_context is not None
                else None
            ),
            "runtime_context": self._runtime_context_summary(),
        }
        rendered_prompt = self._prompts.render("macro_reasoning", reasoning_payload)
        reasoning = self._reasoning_backend.reason(rendered_prompt, reasoning_payload)
        plan = self._normalize_execution_plan(reasoning, shared_structure_context=shared_structure_context)
        raw_result = self._tool.invoke(
            smiles=smiles,
            shared_structure_context=shared_structure_context,
            focus_areas=plan.focus_areas,
        )
        task_completion_status, task_completion_text = self._task_completion(plan)
        render_payload = {
            "task_received": task_received,
            "current_hypothesis": current_hypothesis,
            "tool_name": self._tool.name,
            "task_completion_text": task_completion_text,
            "shared_context_note": self._shared_context_note(shared_structure_context),
            "reasoning_summary_text": reasoning.reasoning_summary,
            "capability_limit_note": reasoning.capability_limit_note,
            "focus_areas_text": ", ".join(plan.focus_areas) if plan.focus_areas else "general macro structural evidence",
            "plan_steps": self._plan_steps_text(plan),
            "result_summary_text": self._successful_result_summary(raw_result),
            "local_uncertainty_detail": self._remaining_uncertainty_text(shared_structure_context),
            "aromatic_atom_count": raw_result["aromatic_atom_count"],
            "hetero_atom_count": raw_result["hetero_atom_count"],
            "branch_point_count": raw_result["branch_point_count"],
            "conjugation_proxy": raw_result["conjugation_proxy"],
            "flexibility_proxy": raw_result["flexibility_proxy"],
            "rotatable_bond_count": raw_result["rotor_topology"]["rotatable_bond_count"],
            "aromatic_ring_count": raw_result["ring_and_conjugation_summary"]["aromatic_ring_count"],
            "ring_system_count": raw_result["ring_and_conjugation_summary"]["ring_system_count"],
            "donor_acceptor_partition_proxy": raw_result["donor_acceptor_layout"]["donor_acceptor_partition_proxy"],
            "planarity_proxy": raw_result["planarity_and_torsion_summary"]["planarity_proxy"],
            "compactness_proxy": raw_result["compactness_and_contact_proxies"]["compactness_proxy"],
            "conformer_dispersion_proxy": raw_result["conformer_dispersion_summary"]["conformer_dispersion_proxy"],
        }
        rendered = self._prompts.render_sections("macro_specialized", render_payload)
        tool_call_parts = [f"focus_areas={plan.focus_areas!r}"]
        if shared_structure_context is not None:
            tool_call_parts.append(f"shared_xyz='{shared_structure_context.prepared_xyz_path}'")
        tool_calls = [f"{self._tool.name}(smiles='{smiles}', {', '.join(tool_call_parts)})"]

        return AgentReport(
            agent_name="macro",
            task_received=task_received,
            task_completion_status=task_completion_status,
            task_completion=rendered["task_completion"],
            task_understanding=reasoning.task_understanding,
            reasoning_summary=rendered["reasoning_summary"],
            execution_plan=rendered["execution_plan"],
            result_summary=rendered["result_summary"],
            remaining_local_uncertainty=rendered["remaining_local_uncertainty"],
            tool_calls=tool_calls,
            raw_results={"macro_structure_scan": raw_result, "reasoning_output": reasoning.model_dump(mode="json")},
            structured_results={
                **raw_result,
                "task_completion_status": task_completion_status,
                "task_completion": rendered["task_completion"],
                "reasoning": reasoning.model_dump(mode="json"),
                "execution_plan": plan.model_dump(mode="json"),
                "supported_scope": list(plan.supported_scope),
                "unsupported_requests": list(plan.unsupported_requests),
            },
            generated_artifacts={},
            status="success",
            planner_readable_report=rendered["planner_readable_report"],
        )

    def _build_reasoning_backend(
        self,
        config: AieMasConfig,
        llm_client: Optional[OpenAICompatibleMacroClient],
    ) -> MacroReasoningBackend:
        return OpenAIMacroReasoningBackend(config, client=llm_client)

    def _normalize_execution_plan(
        self,
        reasoning: MacroReasoningResponse,
        *,
        shared_structure_context: Optional[SharedStructureContext],
    ) -> MacroExecutionPlan:
        structure_source = (
            "shared_prepared_structure"
            if shared_structure_context is not None
            else "smiles_only_fallback"
        )
        steps = [
            MacroExecutionStep(
                step_id="shared_context_load",
                step_type="shared_context_load",
                description=(
                    "Load the shared prepared structure context and reuse its descriptors."
                    if shared_structure_context is not None
                    else "Load a SMILES-only fallback context because shared structure preparation was unavailable."
                ),
                input_source="shared_structure_context" if shared_structure_context is not None else "smiles",
                expected_outputs=["structure_source resolution"],
            ),
            MacroExecutionStep(
                step_id="focus_selection",
                step_type="focus_selection",
                description="Select the macro structural focus areas requested by the Planner instruction.",
                input_source="task_instruction",
                expected_outputs=["focus areas"],
            ),
            MacroExecutionStep(
                step_id="topology_analysis",
                step_type="topology_analysis",
                description="Summarize rotor topology, ring systems, conjugation, and donor-acceptor layout.",
                input_source=structure_source,
                expected_outputs=["rotor topology", "ring and conjugation summary", "donor-acceptor layout"],
            ),
            MacroExecutionStep(
                step_id="geometry_proxy_analysis",
                step_type="geometry_proxy_analysis",
                description="Summarize planarity, torsion, compactness, and conformer-dispersion proxies.",
                input_source=structure_source,
                expected_outputs=[
                    "planarity and torsion summary",
                    "compactness and contact proxies",
                    "conformer dispersion summary",
                ],
            ),
        ]
        return MacroExecutionPlan(
            local_goal=reasoning.execution_plan.local_goal,
            requested_deliverables=list(reasoning.execution_plan.requested_deliverables),
            structure_source=structure_source,  # type: ignore[arg-type]
            focus_areas=list(reasoning.execution_plan.focus_areas),
            supported_scope=[
                "rotor topology summary",
                "ring and conjugation summary",
                "donor-acceptor layout",
                "planarity and torsion summary",
                "compactness and contact proxies",
                "conformer dispersion summary",
            ],
            unsupported_requests=list(reasoning.execution_plan.unsupported_requests),
            steps=steps,
            expected_outputs=list(reasoning.expected_outputs),
            failure_reporting=reasoning.failure_policy,
        )

    def _runtime_context_summary(self) -> dict[str, Any]:
        return {
            "macro_backend": self._config.macro_backend,
            "tool_backend": self._config.tool_backend,
            "macro_model": self._config.macro_model,
            "macro_temperature": self._config.macro_temperature,
            "macro_timeout_seconds": self._config.macro_timeout_seconds,
            "supported_scope": [
                "shared prepared structure reuse",
                "SMILES-only structural fallback",
                "deterministic low-cost topology analysis",
                "deterministic low-cost geometry proxy analysis",
            ],
            "unsupported_scope": [
                "packing simulation",
                "aggregate-state modeling",
                "heavy global conformer search",
                "global mechanism adjudication",
            ],
        }

    def _shared_context_note(self, shared_structure_context: Optional[SharedStructureContext]) -> str:
        if shared_structure_context is None:
            return "Shared 3D structure context is unavailable, so this macro run uses SMILES-only fallback proxies."
        return (
            "Shared 3D structure context is available and reused from "
            f"{shared_structure_context.prepared_xyz_path}."
        )

    def _remaining_uncertainty_text(
        self,
        shared_structure_context: Optional[SharedStructureContext],
    ) -> str:
        if shared_structure_context is None:
            return (
                "Macro evidence is limited to SMILES-only fallback proxies and still cannot resolve excited-state relaxation "
                "behavior, aggregation-state packing, or external consistency."
            )
        return (
            "Macro evidence is limited to single-molecule low-cost structural and geometry proxies, so it still cannot "
            "resolve excited-state relaxation behavior, aggregation-state packing, or external consistency."
        )

    def _plan_steps_text(self, plan: MacroExecutionPlan) -> str:
        return " ".join(f"[{step.step_id}] {step.description}" for step in plan.steps)

    def _successful_result_summary(self, raw_result: dict[str, Any]) -> str:
        return (
            f"The macro scan recorded aromatic_atom_count={raw_result['aromatic_atom_count']}, "
            f"hetero_atom_count={raw_result['hetero_atom_count']}, "
            f"branch_point_count={raw_result['branch_point_count']}, "
            f"rotatable_bond_count={raw_result['rotor_topology']['rotatable_bond_count']}, "
            f"planarity_proxy={raw_result['planarity_and_torsion_summary']['planarity_proxy']}, "
            f"compactness_proxy={raw_result['compactness_and_contact_proxies']['compactness_proxy']}, and "
            f"conformer_dispersion_proxy={raw_result['conformer_dispersion_summary']['conformer_dispersion_proxy']}."
        )

    def _task_completion(self, plan: MacroExecutionPlan) -> tuple[str, str]:
        if plan.unsupported_requests:
            unsupported = "; ".join(plan.unsupported_requests)
            return (
                "partial",
                "Task only partially completed. The agent returned bounded macro evidence, but it could not "
                f"complete unsupported parts of the Planner instruction: {unsupported}.",
            )
        return (
            "completed",
            "Task completed successfully within current macro capability.",
        )
