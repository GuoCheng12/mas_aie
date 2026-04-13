from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Protocol

from pydantic import BaseModel, Field

from aie_mas.compat.langchain import prompt_value_to_messages
from aie_mas.config import AieMasConfig
from aie_mas.graph.state import (
    AgentFramingMode,
    AgentReport,
    CliActionSpec,
    MacroCapabilityName,
    MacroExecutionPlan,
    MacroExecutionStep,
    MacroToolPlan,
    MacroToolRequest,
    MacroTranslationBindingMode,
    ReasoningPhase,
    SharedStructureContext,
)
from aie_mas.llm.openai_compatible import OpenAICompatibleMacroClient
from aie_mas.tools.cli_execution import (
    CliExecutionError,
    execute_cli_action,
    macro_command_id,
    render_cli_command_catalog,
)
from aie_mas.tools.macro import (
    MACRO_ACTION_REGISTRY,
    MACRO_CAPABILITY_REGISTRY,
    DeterministicMacroStructureTool,
)
from aie_mas.utils.prompts import PromptRepository


def _default_prompt_repository() -> PromptRepository:
    return PromptRepository(Path(__file__).resolve().parents[1] / "prompts")


class MacroReasoningPlanDraft(BaseModel):
    local_goal: str
    requested_deliverables: list[str] = Field(default_factory=list)
    selected_capability: Optional[MacroCapabilityName] = None
    requested_observable_tags: list[str] = Field(default_factory=list)
    focus_areas: list[str] = Field(default_factory=list)
    unsupported_requests: list[str] = Field(default_factory=list)


class MacroReasoningResponse(BaseModel):
    task_understanding: str
    reasoning_summary: str
    cli_action: CliActionSpec | None = None
    unsupported_requests: list[str] = Field(default_factory=list)
    execution_plan: MacroReasoningPlanDraft | None = None
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
        reasoning_phase: ReasoningPhase = "portfolio_screening",
        agent_framing_mode: AgentFramingMode = "portfolio_neutral",
        screening_focus_hypotheses: Optional[list[str]] = None,
        screening_focus_summary: Optional[str] = None,
        recent_rounds_context: Optional[list[dict[str, object]]] = None,
        shared_structure_context: Optional[SharedStructureContext] = None,
        case_id: Optional[str] = None,
        round_index: int = 1,
    ) -> AgentReport:
        del case_id, round_index
        recent_rounds_context = recent_rounds_context or []
        screening_focus_hypotheses = screening_focus_hypotheses or []
        reasoning_payload = {
            "current_hypothesis": current_hypothesis,
            "reasoning_phase": reasoning_phase,
            "agent_framing_mode": agent_framing_mode,
            "screening_focus_hypotheses": screening_focus_hypotheses,
            "screening_focus_summary": screening_focus_summary,
            "task_instruction": task_received,
            "recent_rounds_context": recent_rounds_context,
            "shared_structure_context": (
                shared_structure_context.model_dump(mode="json")
                if shared_structure_context is not None
                else None
            ),
            "runtime_context": self._runtime_context_summary(),
        }
        retry_history: list[dict[str, Any]] = []
        previous_cli_failure_context: dict[str, Any] | None = None
        cli_action: CliActionSpec | None = None
        compatibility_plan: MacroExecutionPlan | None = None
        reasoning: MacroReasoningResponse | None = None
        cli_result = None
        for retry_index in range(self._config.cli_local_retry_attempts + 1):
            attempt_payload = {
                **reasoning_payload,
                "cli_retry_attempt_index": retry_index,
                "previous_cli_failure_context": previous_cli_failure_context,
            }
            rendered_prompt = self._prompts.render("macro_reasoning", attempt_payload)
            reasoning = self._reasoning_backend.reason(rendered_prompt, attempt_payload)
            cli_action = self._normalize_cli_action(
                reasoning,
                task_received=task_received,
                smiles=smiles,
                shared_structure_context=shared_structure_context,
            )
            compatibility_plan = self._build_compatibility_execution_plan(
                reasoning,
                task_received=task_received,
                shared_structure_context=shared_structure_context,
            )
            try:
                cli_result = execute_cli_action(
                    config=self._config,
                    action=cli_action,
                    expected_agent_name="macro",
                )
                break
            except CliExecutionError as exc:
                failure_context = self._cli_failure_context(
                    retry_index=retry_index,
                    action=cli_action,
                    error=exc,
                )
                retry_history.append(failure_context)
                previous_cli_failure_context = failure_context
                if retry_index >= self._config.cli_local_retry_attempts:
                    assert reasoning is not None
                    assert compatibility_plan is not None
                    return AgentReport(
                        agent_name="macro",
                        task_received=task_received,
                        task_completion_status="failed",
                        task_completion="Task failed because the bounded macro CLI execution did not complete successfully.",
                        task_understanding=reasoning.task_understanding,
                        reasoning_summary=reasoning.reasoning_summary,
                        execution_plan="Macro CLI execution failed before a local result payload could be returned.",
                        result_summary=f"Macro CLI execution failed: {exc}",
                        remaining_local_uncertainty="No bounded macro result was produced because the CLI execution layer failed.",
                        tool_calls=[f"{cli_action.command_program} {' '.join(cli_action.command_args)}"],
                        raw_results={
                            "cli_error": {
                                "message": str(exc),
                                "stdout": exc.stdout,
                                "stderr": exc.stderr,
                            },
                            "cli_retry_history": retry_history,
                            "reasoning_output": reasoning.model_dump(mode="json"),
                        },
                        structured_results={
                            "status": "failed",
                            "operational_status": "execution_failed",
                            "failure_classification": "execution_failed",
                            "command_id": cli_action.command_id,
                            "command_program": cli_action.command_program,
                            "command_args": list(cli_action.command_args),
                            "stdin_payload_summary": dict(cli_action.stdin_payload),
                            "cli_exit_code": exc.exit_code,
                            "cli_stdout_excerpt": exc.stdout,
                            "cli_stderr_excerpt": exc.stderr,
                            "requested_capability": compatibility_plan.selected_capability,
                            "selected_capability": compatibility_plan.selected_capability,
                            "executed_capability": cli_action.command_id,
                            "performed_new_calculations": cli_action.perform_new_calculation,
                            "reused_existing_artifacts": cli_action.reused_existing_artifacts,
                            "binding_mode": cli_action.binding_mode,
                            "requested_observable_tags": list(cli_action.requested_observable_tags),
                            "covered_observable_tags": [],
                            "missing_deliverables": list(reasoning.expected_outputs),
                            "resolved_target_ids": dict(cli_action.resolved_target_ids),
                            "planner_requested_capability": compatibility_plan.selected_capability,
                            "translation_substituted_action": False,
                            "translation_substitution_reason": "",
                            "fulfillment_mode": None,
                            "error": {
                                "message": str(exc),
                                "stdout": exc.stdout,
                                "stderr": exc.stderr,
                            },
                            "cli_retry_attempts_used": len(retry_history),
                            "cli_retry_history": retry_history,
                        },
                        generated_artifacts={},
                        status="failed",
                        planner_readable_report="Task completion: bounded macro CLI execution failed before any local macro evidence could be returned.",
                    )
        assert reasoning is not None
        assert cli_action is not None
        assert compatibility_plan is not None
        assert cli_result is not None
        raw_result = dict(cli_result.parsed_json)
        task_completion_status, task_completion_text = self._task_completion(compatibility_plan, raw_result)
        executed_capability = str(raw_result.get("executed_capability") or compatibility_plan.selected_capability or "").strip()
        render_payload = {
            "task_received": task_received,
            "current_hypothesis": current_hypothesis,
            "framing_note": self._framing_note(
                current_hypothesis=current_hypothesis,
                reasoning_phase=reasoning_phase,
                agent_framing_mode=agent_framing_mode,
                screening_focus_hypotheses=screening_focus_hypotheses,
                screening_focus_summary=screening_focus_summary,
            ),
            "tool_name": self._tool.name,
            "task_completion_text": task_completion_text,
            "shared_context_note": self._shared_context_note(shared_structure_context),
            "reasoning_summary_text": reasoning.reasoning_summary,
            "capability_limit_note": reasoning.capability_limit_note,
            "selected_capability": cli_action.command_id,
            "focus_areas_text": ", ".join(compatibility_plan.focus_areas) if compatibility_plan.focus_areas else "general macro structural evidence",
            "plan_steps": self._plan_steps_text(compatibility_plan),
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
        tool_call_parts = [f"command_id='{cli_action.command_id}'"]
        if shared_structure_context is not None:
            tool_call_parts.append(f"shared_xyz='{shared_structure_context.prepared_xyz_path}'")
        tool_calls = [f"{cli_action.command_program} {' '.join(cli_action.command_args)} ({', '.join(tool_call_parts)})"]

        structured_results = {
            **raw_result,
            "operational_status": "completed",
            "failure_classification": None,
            "command_id": cli_action.command_id,
            "command_program": cli_action.command_program,
            "command_args": list(cli_action.command_args),
            "stdin_payload_summary": dict(cli_result.stdin_payload_summary),
            "cli_exit_code": cli_result.cli_exit_code,
            "cli_stdout_excerpt": cli_result.cli_stdout_excerpt,
            "cli_stderr_excerpt": cli_result.cli_stderr_excerpt,
            "cli_retry_attempts_used": len(retry_history),
            "cli_retry_history": retry_history,
            "task_completion_status": task_completion_status,
            "task_completion": rendered["task_completion"],
            "reasoning": reasoning.model_dump(mode="json"),
            "cli_action": cli_action.model_dump(mode="json"),
            "execution_plan": compatibility_plan.model_dump(mode="json"),
            "supported_scope": list(compatibility_plan.supported_scope),
            "unsupported_requests": list(reasoning.unsupported_requests or compatibility_plan.unsupported_requests),
            "requested_capability": raw_result.get("requested_capability") or compatibility_plan.selected_capability,
            "selected_capability": raw_result.get("selected_capability") or compatibility_plan.selected_capability,
            "executed_capability": cli_action.command_id,
            "performed_new_calculations": cli_action.perform_new_calculation,
            "reused_existing_artifacts": cli_action.reused_existing_artifacts,
            "binding_mode": raw_result.get("binding_mode") or cli_action.binding_mode,
            "requested_observable_tags": list(
                raw_result.get("requested_observable_tags") or cli_action.requested_observable_tags
            ),
            "covered_observable_tags": list(raw_result.get("covered_observable_tags") or []),
            "missing_deliverables": list(raw_result.get("missing_deliverables") or []),
            "resolved_target_ids": dict(raw_result.get("resolved_target_ids") or cli_action.resolved_target_ids),
            "planner_requested_capability": raw_result.get("planner_requested_capability") or compatibility_plan.selected_capability,
            "translation_substituted_action": bool(raw_result.get("translation_substituted_action")),
            "translation_substitution_reason": str(raw_result.get("translation_substitution_reason") or ""),
            "fulfillment_mode": str(raw_result.get("fulfillment_mode") or ""),
            "route_summary": raw_result.get("route_summary") or {},
        }

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
            raw_results={
                "macro_structure_scan": raw_result,
                "reasoning_output": reasoning.model_dump(mode="json"),
                "cli_command_result": cli_result.model_dump(mode="json"),
                "cli_retry_history": retry_history,
            },
            structured_results=structured_results,
            generated_artifacts={},
            status="success",
            planner_readable_report=rendered["planner_readable_report"],
        )

    def _framing_note(
        self,
        *,
        current_hypothesis: str,
        reasoning_phase: ReasoningPhase,
        agent_framing_mode: AgentFramingMode,
        screening_focus_hypotheses: list[str],
        screening_focus_summary: Optional[str],
    ) -> str:
        focus_text = ", ".join(screening_focus_hypotheses) if screening_focus_hypotheses else "none"
        summary_text = screening_focus_summary or "No screening focus summary was provided."
        if agent_framing_mode == "portfolio_neutral":
            return (
                f"Current reasoning phase: {reasoning_phase}. "
                f"Agent framing mode: {agent_framing_mode}. "
                f"The provisional top1 is '{current_hypothesis}' for bookkeeping only; do not treat it as settled. "
                f"Use this macro task to screen still-credible alternatives. "
                f"Screening focus hypotheses: {focus_text}. "
                f"Screening focus summary: {summary_text}"
            )
        return (
            f"Current reasoning phase: {reasoning_phase}. "
            f"Agent framing mode: {agent_framing_mode}. "
            f"Anchor this macro task to current working hypothesis '{current_hypothesis}'. "
            f"Screening focus summary: {summary_text}"
        )

    def _build_reasoning_backend(
        self,
        config: AieMasConfig,
        llm_client: Optional[OpenAICompatibleMacroClient],
    ) -> MacroReasoningBackend:
        return OpenAIMacroReasoningBackend(config, client=llm_client)

    def _build_compatibility_execution_plan(
        self,
        reasoning: MacroReasoningResponse,
        *,
        task_received: str,
        shared_structure_context: Optional[SharedStructureContext],
    ) -> MacroExecutionPlan:
        structure_source = (
            "shared_prepared_structure"
            if shared_structure_context is not None
            else "smiles_only_fallback"
        )
        requested_capability = self._requested_capability_from_task(task_received)
        binding_mode = self._binding_mode_from_task(task_received, requested_capability)
        selected_capability = self._resolve_selected_capability(
            reasoning=reasoning,
            task_received=task_received,
            shared_structure_context=shared_structure_context,
            requested_capability=requested_capability,
        )
        action_definition = MACRO_ACTION_REGISTRY[selected_capability]
        requested_observable_tags = list(reasoning.execution_plan.requested_observable_tags if reasoning.execution_plan is not None else [])
        if not requested_observable_tags:
            requested_observable_tags = list(action_definition.exact_observable_tags)
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
                description="Translate the Planner instruction into one bounded registry-backed macro capability.",
                input_source="task_instruction",
                expected_outputs=["selected macro capability", "requested observable tags"],
            ),
            MacroExecutionStep(
                step_id="topology_analysis",
                step_type="topology_analysis",
                description=f"Collect deterministic structural evidence for `{selected_capability}` from the available structure source.",
                input_source=structure_source,
                expected_outputs=list(action_definition.default_deliverables),
            ),
            MacroExecutionStep(
                step_id="geometry_proxy_analysis",
                step_type="geometry_proxy_analysis",
                description="Summarize only bounded local structural or geometry-proxy outputs and record any missing deliverables.",
                input_source=structure_source,
                expected_outputs=list(action_definition.exact_observable_tags),
            ),
        ]
        macro_tool_request = MacroToolRequest(
            capability_name=selected_capability,
            structure_target=action_definition.structure_target,
            reuse_shared_structure_only=shared_structure_context is not None,
            requested_observable_scope=requested_observable_tags,
            requested_route_summary=action_definition.purpose,
            honor_exact_target=binding_mode == "hard",
            allow_fallback=binding_mode != "hard",
        )
        macro_tool_plan = MacroToolPlan(
            calls=[
                {
                    "call_id": f"execute_{selected_capability}",
                    "call_kind": "execution",
                    "request": macro_tool_request.model_dump(mode="json"),
                }
            ],
            requested_route_summary=action_definition.purpose,
            requested_deliverables=list(reasoning.execution_plan.requested_deliverables)
            if reasoning.execution_plan is not None
            else list(action_definition.default_deliverables),
        )
        return MacroExecutionPlan(
            local_goal=(
                reasoning.execution_plan.local_goal
                if reasoning.execution_plan is not None
                else f"Execute bounded macro command `{macro_command_id(selected_capability)}`."
            ),
            requested_deliverables=(
                list(reasoning.execution_plan.requested_deliverables)
                if reasoning.execution_plan is not None and reasoning.execution_plan.requested_deliverables
                else list(action_definition.default_deliverables)
            ),
            structure_source=structure_source,  # type: ignore[arg-type]
            selected_capability=selected_capability,
            binding_mode=binding_mode,
            requested_observable_tags=requested_observable_tags,
            resolved_target_ids=self._resolved_target_ids(shared_structure_context),
            focus_areas=list(reasoning.execution_plan.focus_areas if reasoning.execution_plan is not None else []),
            supported_scope=[definition.name for definition in MACRO_CAPABILITY_REGISTRY.values()],
            unsupported_requests=list(reasoning.unsupported_requests or (reasoning.execution_plan.unsupported_requests if reasoning.execution_plan is not None else [])),
            steps=steps,
            expected_outputs=list(reasoning.expected_outputs),
            failure_reporting=reasoning.failure_policy,
            macro_tool_request=macro_tool_request,
            macro_tool_plan=macro_tool_plan,
        )

    def _normalize_cli_action(
        self,
        reasoning: MacroReasoningResponse,
        *,
        task_received: str,
        smiles: str,
        shared_structure_context: Optional[SharedStructureContext],
    ) -> CliActionSpec:
        requested_capability = self._requested_capability_from_task(task_received)
        binding_mode = self._binding_mode_from_task(task_received, requested_capability)
        selected_capability = self._resolve_selected_capability(
            reasoning=reasoning,
            task_received=task_received,
            shared_structure_context=shared_structure_context,
            requested_capability=requested_capability,
        )
        command_id = macro_command_id(selected_capability)
        action_definition = MACRO_ACTION_REGISTRY[selected_capability]
        requested_observable_tags = (
            list(reasoning.execution_plan.requested_observable_tags)
            if reasoning.execution_plan is not None
            else list(action_definition.exact_observable_tags)
        )
        canonical_stdin_payload = {
            "selected_capability": selected_capability,
            "requested_capability": requested_capability or selected_capability,
            "requested_observable_tags": requested_observable_tags,
            "requested_deliverables": (
                list(reasoning.execution_plan.requested_deliverables)
                if reasoning.execution_plan is not None and reasoning.execution_plan.requested_deliverables
                else list(action_definition.default_deliverables)
            ),
            "binding_mode": binding_mode,
            "smiles": smiles,
            "shared_structure_context": (
                shared_structure_context.model_dump(mode="json")
                if shared_structure_context is not None
                else None
            ),
        }
        action = reasoning.cli_action
        if action is not None and action.command_id == command_id:
            merged_stdin_payload = dict(action.stdin_payload)
            merged_stdin_payload.update(canonical_stdin_payload)
            return action.model_copy(
                update={
                    "command_program": "python3",
                    "command_args": ["-m", "aie_mas.macro_harness.cli", "execute-payload"],
                    "stdin_payload": merged_stdin_payload,
                }
            )
        return CliActionSpec(
            command_id=command_id,
            command_program="python3",
            command_args=["-m", "aie_mas.macro_harness.cli", "execute-payload"],
            stdin_payload=canonical_stdin_payload,
            expected_outputs=list(reasoning.expected_outputs),
            perform_new_calculation=False,
            reused_existing_artifacts=shared_structure_context is not None,
            resolved_target_ids=self._resolved_target_ids(shared_structure_context),
            binding_mode=binding_mode,
            requested_observable_tags=requested_observable_tags,
        )

    def _runtime_context_summary(self) -> dict[str, Any]:
        return {
            "macro_backend": self._config.macro_backend,
            "macro_model": self._config.macro_model,
            "macro_temperature": self._config.macro_temperature,
            "macro_timeout_seconds": self._config.macro_timeout_seconds,
            "cli_local_retry_attempts": self._config.cli_local_retry_attempts,
            "supported_scope": [definition.name for definition in MACRO_CAPABILITY_REGISTRY.values()],
            "unsupported_scope": [
                "packing simulation",
                "aggregate-state modeling",
                "heavy global conformer search",
                "global mechanism adjudication",
            ],
            "command_catalog": render_cli_command_catalog("macro"),
            "capability_registry": {
                name: {
                    "purpose": definition.purpose,
                    "structure_target": definition.structure_target,
                    "supported_deliverables": list(definition.supported_deliverables),
                    "evidence_goal_tags": list(definition.evidence_goal_tags),
                    "exact_observable_tags": list(definition.exact_observable_tags),
                    "unsupported_requests_note": definition.unsupported_requests_note,
                }
                for name, definition in MACRO_CAPABILITY_REGISTRY.items()
            },
        }

    def _cli_failure_context(
        self,
        *,
        retry_index: int,
        action: CliActionSpec,
        error: CliExecutionError,
    ) -> dict[str, Any]:
        return {
            "retry_index": retry_index,
            "command_id": action.command_id,
            "command_program": action.command_program,
            "command_args": list(action.command_args),
            "stdin_payload": dict(action.stdin_payload),
            "message": str(error),
            "cli_exit_code": error.exit_code,
            "cli_stdout_excerpt": error.stdout,
            "cli_stderr_excerpt": error.stderr,
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
        capability_summary = str(raw_result.get("capability_result_summary") or "").strip()
        metrics_summary = (
            f"The macro scan recorded aromatic_atom_count={raw_result['aromatic_atom_count']}, "
            f"hetero_atom_count={raw_result['hetero_atom_count']}, "
            f"branch_point_count={raw_result['branch_point_count']}, "
            f"rotatable_bond_count={raw_result['rotor_topology']['rotatable_bond_count']}, "
            f"planarity_proxy={raw_result['planarity_and_torsion_summary']['planarity_proxy']}, "
            f"compactness_proxy={raw_result['compactness_and_contact_proxies']['compactness_proxy']}, and "
            f"conformer_dispersion_proxy={raw_result['conformer_dispersion_summary']['conformer_dispersion_proxy']}."
        )
        if capability_summary:
            return f"{capability_summary} {metrics_summary}"
        return metrics_summary

    def _task_completion(self, plan: MacroExecutionPlan, raw_result: dict[str, Any]) -> tuple[str, str]:
        missing_deliverables = list(raw_result.get("missing_deliverables") or [])
        if plan.unsupported_requests or missing_deliverables:
            detail_parts: list[str] = []
            if plan.unsupported_requests:
                detail_parts.append("; ".join(plan.unsupported_requests))
            if missing_deliverables:
                detail_parts.append(f"Missing deliverables: {'; '.join(missing_deliverables)}.")
            return (
                "contracted",
                "Task was completed only in a capability-limited contracted form. The agent returned bounded macro evidence, but it could not "
                f"complete unsupported parts of the Planner instruction: {' '.join(detail_parts)}",
            )
        return (
            "completed",
            "Task completed successfully within current macro capability.",
        )

    def _requested_capability_from_task(self, task_received: str) -> Optional[MacroCapabilityName]:
        lowered = task_received.lower()
        for capability_name in MACRO_CAPABILITY_REGISTRY:
            if capability_name in lowered:
                return capability_name
        return None

    def _binding_mode_from_task(
        self,
        task_received: str,
        requested_capability: Optional[MacroCapabilityName],
    ) -> MacroTranslationBindingMode:
        if requested_capability is None:
            return "none"
        lowered = task_received.lower()
        if "execute only" in lowered or "exactly one registry-backed" in lowered:
            return "hard"
        return "preferred"

    def _resolve_selected_capability(
        self,
        *,
        reasoning: MacroReasoningResponse,
        task_received: str,
        shared_structure_context: Optional[SharedStructureContext],
        requested_capability: Optional[MacroCapabilityName],
    ) -> MacroCapabilityName:
        if reasoning.execution_plan is not None and reasoning.execution_plan.selected_capability in MACRO_CAPABILITY_REGISTRY:
            return reasoning.execution_plan.selected_capability
        if reasoning.cli_action is not None and reasoning.cli_action.command_id.startswith("macro."):
            candidate = reasoning.cli_action.command_id.split(".", 1)[1]
            if candidate in MACRO_CAPABILITY_REGISTRY:
                return candidate  # type: ignore[return-value]
        if requested_capability is not None:
            return requested_capability
        focus_areas = [item.lower() for item in (reasoning.execution_plan.focus_areas if reasoning.execution_plan is not None else [])]
        task_lower = task_received.lower()
        capability_by_token: list[tuple[MacroCapabilityName, tuple[str, ...]]] = [
            (
                "screen_intramolecular_hbond_preorganization",
                ("h-bond", "hydrogen bond", "proton", "esipt", "o-h", "phenolic", "imine"),
            ),
            ("screen_rotor_torsion_topology", ("rotor", "torsion", "twist")),
            ("screen_donor_acceptor_layout", ("donor-acceptor", "donor acceptor", "charge transfer", "layout", "partition")),
            ("screen_conformer_geometry_proxy", ("conformer", "dispersion")),
            ("screen_neutral_aromatic_structure", ("neutral aromatic", "aromatic core", "ring-system", "ring system")),
            ("screen_planarity_compactness", ("planarity", "compactness", "principal span")),
        ]
        for capability_name, tokens in capability_by_token:
            if any(token in task_lower for token in tokens):
                return capability_name
            if any(token in area for area in focus_areas for token in tokens):
                return capability_name
        if shared_structure_context is not None:
            return "screen_planarity_compactness"
        return "screen_donor_acceptor_layout"

    def _resolved_target_ids(
        self,
        shared_structure_context: Optional[SharedStructureContext],
    ) -> dict[str, Any]:
        if shared_structure_context is None:
            return {"structure_source": "smiles_only_fallback"}
        return {
            "structure_source": "shared_prepared_structure",
            "prepared_xyz_path": shared_structure_context.prepared_xyz_path,
            "prepared_sdf_path": shared_structure_context.prepared_sdf_path,
            "selected_conformer_id": shared_structure_context.selected_conformer_id,
        }
