from __future__ import annotations

from aie_mas.graph.state import AgentReport, MicroscopicTaskSpec, SharedStructureStatus

from .interpreter import MicroscopicReasoningOutcome
from .compiler import MicroscopicReasoningParseError, _closest_supported_actions_for_unsupported_parts


class MicroscopicReportingMixin:
    def _reasoning_parse_failure_report(
        self,
        *,
        task_received: str,
        task_spec: MicroscopicTaskSpec,
        current_hypothesis: str,
        parse_error: MicroscopicReasoningParseError,
    ) -> AgentReport:
        contract_errors = list(parse_error.contract_errors)
        completion_reason_code = self._registry_completion_code_for_parse_error(contract_errors)
        contract_error_text = "; ".join(contract_errors) if contract_errors else "No parser diagnostics were recorded."
        task_completion_text = (
            "Task could not be completed because the local microscopic action decision could not be parsed into a valid bounded execution plan."
        )
        result_summary_text = (
            "Microscopic reasoning stopped before tool runtime because the local action-decision translation was invalid. "
            f"Diagnostics: {contract_error_text}"
        )
        render_payload = {
            "task_received": task_received,
            "current_hypothesis": current_hypothesis,
            "requested_focus": ", ".join(self._requested_deliverables(task_received, task_spec)),
            "capability_route": "baseline_bundle",
            "requested_capability": "unknown",
            "executed_capability": "unknown",
            "performed_new_calculations": "false",
            "reused_existing_artifacts": "false",
            "resolved_target_ids_text": "No target IDs were resolved because reasoning stopped before tool runtime.",
            "honored_constraints_text": "No honored constraints were recorded because reasoning stopped before tool runtime.",
            "unmet_constraints_text": contract_error_text,
            "missing_deliverables_text": "No deliverables were produced because tool execution never started.",
            "requested_route_summary": "Microscopic local action interpretation could not be compiled into a bounded execution route.",
            "task_completion_text": task_completion_text,
            "recent_context_note": "No microscopic tool runtime was attempted because action-decision parsing failed.",
            "capability_scope": self._capability_scope_text(),
            "structure_source_note": "Tool execution did not start because the local action decision could not be compiled.",
            "unsupported_requests_note": self._unsupported_requests_note(self._unsupported_requests(task_received, task_spec)),
            "reasoning_summary_text": "Microscopic action-decision parsing failed before a valid local execution plan could be compiled.",
            "capability_limit_note": "Current microscopic execution requires a valid structured action decision or a valid migration fallback representation.",
            "failure_policy": "Return a local failed report and preserve parser diagnostics for Planner review.",
            "plan_steps": "No execution steps were compiled because action-decision parsing failed.",
            "expected_outputs_text": "No outputs were produced because tool execution never started.",
            "result_summary_text": result_summary_text,
            "local_uncertainty_detail": (
                "the Planner did not receive new microscopic evidence because local action-decision parsing failed before any Amesp execution could begin"
            ),
        }
        rendered = self._prompts.render_sections("microscopic_amesp_specialized", render_payload)
        structured_results = {
            "backend": "amesp",
            "reasoning_backend": self._config.microscopic_backend,
            "task_mode": task_spec.mode,
            "task_label": task_spec.task_label,
            "task_objective": task_spec.objective,
            "task_completion_status": "failed",
            "completion_reason_code": completion_reason_code,
            "task_completion": rendered["task_completion"],
            "reasoning": {
                "task_understanding": "Microscopic reasoning could not be parsed into a valid structured action decision.",
                "reasoning_summary": "No valid bounded execution route was compiled.",
                "failure_policy": "Return parser diagnostics only.",
            },
            "reasoning_parse_mode": "failed",
            "reasoning_contract_mode": parse_error.contract_mode,
            "reasoning_contract_errors": contract_errors,
            "microscopic_action_status": "unsupported",
            "unsupported_intent": None,
            "unsupported_parts": [],
            "closest_supported_actions": [],
            "registry_action_name": None,
            "registry_validation_errors": list(contract_errors),
            "registry_infeasible_for_verifier_handshake": completion_reason_code == "action_not_supported_by_registry",
            "registry_infeasible_reason": (
                "action_not_supported_by_registry"
                if completion_reason_code == "action_not_supported_by_registry"
                else None
            ),
            "requested_capability": None,
            "executed_capability": None,
            "performed_new_calculations": False,
            "reused_existing_artifacts": False,
            "resolved_target_ids": {},
            "honored_constraints": [],
            "unmet_constraints": list(contract_errors),
                "missing_deliverables": self._requested_deliverables(task_received, task_spec),
            "error": {
                "code": completion_reason_code,
                "message": str(parse_error),
            },
            "supported_scope": [],
            "unsupported_requests": self._unsupported_requests(task_received, task_spec),
            "artifact_bundle_id": None,
            "artifact_bundle_kind": None,
        }
        return AgentReport(
            agent_name="microscopic",
            task_received=task_received,
            task_completion_status="failed",
            completion_reason_code=completion_reason_code,
            task_completion=rendered["task_completion"],
            task_understanding="Microscopic action-decision parsing failed before local execution planning.",
            reasoning_summary=rendered["reasoning_summary"],
            execution_plan=rendered["execution_plan"],
            result_summary=rendered["result_summary"],
            remaining_local_uncertainty=rendered["remaining_local_uncertainty"],
            tool_calls=["microscopic_reasoning(task_instruction_to_action_decision)"],
            raw_results={
                "reasoning_raw_text": parse_error.raw_text,
                "reasoning_contract_errors": contract_errors,
            },
            structured_results=structured_results,
            generated_artifacts={},
            status="failed",
            planner_readable_report=rendered["planner_readable_report"],
        )

    def _shared_structure_unavailable_report(
        self,
        *,
        task_received: str,
        task_spec: MicroscopicTaskSpec,
        current_hypothesis: str,
        outcome: MicroscopicReasoningOutcome,
        shared_structure_status: SharedStructureStatus,
    ) -> AgentReport:
        reasoning = outcome.reasoning_response
        plan = outcome.compiled_execution_plan
        reasoning_parse_mode = outcome.reasoning_parse_mode
        reasoning_contract_mode = outcome.reasoning_contract_mode
        reasoning_contract_errors = list(outcome.reasoning_contract_errors)
        task_completion_text = (
            "Task could not be completed. The requested microscopic instruction depended on a prepared structure, "
            "but shared structure context was unavailable and private structure preparation was not allowed in this path."
        )
        result_summary_text = (
            "Microscopic execution returned status=partial because shared structure context was not available and "
            "the normal graph path does not allow private structure preparation."
        )
        render_payload = {
            "task_received": task_received,
            "current_hypothesis": current_hypothesis,
            "requested_focus": ", ".join(plan.requested_deliverables),
            "capability_route": plan.capability_route,
            "requested_capability": plan.microscopic_tool_request.capability_name,
            "executed_capability": plan.microscopic_tool_request.capability_name,
            "performed_new_calculations": "false",
            "reused_existing_artifacts": "false",
            "resolved_target_ids_text": "No target IDs were resolved because execution stopped before tool runtime.",
            "honored_constraints_text": "No honored constraints were recorded because execution stopped before tool runtime.",
            "unmet_constraints_text": "Shared-structure preconditions were not met before tool execution.",
            "missing_deliverables_text": "No deliverables were produced because execution stopped before tool runtime.",
            "requested_route_summary": plan.requested_route_summary,
            "task_completion_text": task_completion_text,
            "recent_context_note": "No additional microscopic runtime step was executed.",
            "capability_scope": self._capability_scope_text(),
            "structure_source_note": (
                f"Shared structure status is '{shared_structure_status}', so the normal microscopic path stopped before tool execution."
            ),
            "unsupported_requests_note": self._unsupported_requests_note(plan.unsupported_requests),
            "reasoning_summary_text": reasoning.reasoning_summary,
            "capability_limit_note": reasoning.capability_limit_note,
            "failure_policy": reasoning.failure_policy,
            "plan_steps": self._plan_steps_text(plan),
            "expected_outputs_text": ", ".join(plan.expected_outputs),
            "result_summary_text": result_summary_text,
            "local_uncertainty_detail": (
                "shared prepared structure context is unavailable in the normal graph path, so no bounded microscopic runtime "
                "result could be collected without violating the shared-structure-first policy."
            ),
        }
        rendered = self._prompts.render_sections("microscopic_amesp_specialized", render_payload)
        return AgentReport(
            agent_name="microscopic",
            task_received=task_received,
            task_completion_status="failed",
            completion_reason_code="precondition_missing",
            task_completion=rendered["task_completion"],
            task_understanding=reasoning.task_understanding,
            reasoning_summary=rendered["reasoning_summary"],
            execution_plan=rendered["execution_plan"],
            result_summary=rendered["result_summary"],
            remaining_local_uncertainty=rendered["remaining_local_uncertainty"],
            tool_calls=["microscopic_reasoning(task_instruction_to_execution_plan)"],
            raw_results={
                "reasoning_output": reasoning.model_dump(mode="json"),
                "shared_structure_status": shared_structure_status,
            },
            structured_results={
                "backend": "amesp",
                "reasoning_backend": self._config.microscopic_backend,
                "task_mode": task_spec.mode,
                "task_label": task_spec.task_label,
                "task_objective": task_spec.objective,
                "task_completion_status": "failed",
                "completion_reason_code": "precondition_missing",
                "task_completion": rendered["task_completion"],
                "reasoning": reasoning.model_dump(mode="json"),
                "reasoning_parse_mode": reasoning_parse_mode,
                "reasoning_contract_mode": reasoning_contract_mode,
                "reasoning_contract_errors": reasoning_contract_errors,
                "microscopic_action_status": outcome.action_decision.status,
                "unsupported_intent": None,
                "unsupported_parts": list(outcome.action_decision.unsupported_parts),
                "closest_supported_actions": [],
                "registry_action_name": plan.microscopic_tool_request.capability_name,
                "registry_validation_errors": [],
                "registry_infeasible_for_verifier_handshake": False,
                "registry_infeasible_reason": None,
                "execution_plan": plan.model_dump(mode="json"),
                "requested_capability": plan.microscopic_tool_request.capability_name,
                "executed_capability": plan.microscopic_tool_request.capability_name,
                "performed_new_calculations": False,
                "reused_existing_artifacts": False,
                "resolved_target_ids": {},
                "honored_constraints": [],
                "unmet_constraints": ["shared_structure_context was unavailable before tool execution"] + list(
                    plan.planning_unmet_constraints
                ),
                "missing_deliverables": list(plan.requested_deliverables),
                "error": {
                    "code": "shared_structure_unavailable",
                    "message": result_summary_text,
                    "shared_structure_status": shared_structure_status,
                },
                "supported_scope": plan.supported_scope,
                "unsupported_requests": plan.unsupported_requests,
                "artifact_bundle_id": None,
                "artifact_bundle_kind": None,
            },
            generated_artifacts={},
            status="partial",
            planner_readable_report=rendered["planner_readable_report"],
        )

    def _registry_blocked_request_report(
        self,
        *,
        task_received: str,
        task_spec: MicroscopicTaskSpec,
        current_hypothesis: str,
        outcome: MicroscopicReasoningOutcome,
        registry_blocked_requests: list[str],
    ) -> AgentReport:
        reasoning = outcome.reasoning_response
        plan = outcome.compiled_execution_plan
        action_decision = outcome.action_decision
        reasoning_parse_mode = outcome.reasoning_parse_mode
        reasoning_contract_mode = outcome.reasoning_contract_mode
        reasoning_contract_errors = list(outcome.reasoning_contract_errors)
        blocked_note = "; ".join(registry_blocked_requests)
        unsupported_requests = list(
            dict.fromkeys(
                list((plan.unsupported_requests if plan is not None else []) or [])
                + list(action_decision.unsupported_parts)
                + list(registry_blocked_requests)
            )
        )
        closest_supported_actions = _closest_supported_actions_for_unsupported_parts(registry_blocked_requests)
        registry_validation_errors = [
            "Planner requested unsupported registry-blocked microscopic task(s): "
            + blocked_note
            + "."
        ]
        task_completion_text = (
            "Task could not be completed. The Planner requested a microscopic action that is not represented in the "
            f"current Amesp action registry: {blocked_note}."
        )
        result_summary_text = (
            "Microscopic execution did not start because the Planner explicitly requested a registry-unsupported local task. "
            f"Blocked request(s): {blocked_note}. "
            + (
                f"The closest compiled registry action `{plan.microscopic_tool_request.capability_name}` was intentionally not executed."
                if plan is not None and plan.microscopic_tool_request is not None
                else "No substitute microscopic action was executed."
            )
        )
        requested_deliverables = list(plan.requested_deliverables if plan is not None else reasoning.expected_outputs)
        requested_route_summary = (
            plan.requested_route_summary
            if plan is not None
            else "No bounded Amesp action was executed because the requested local intent is unsupported."
        )
        render_payload = {
            "task_received": task_received,
            "current_hypothesis": current_hypothesis,
            "requested_focus": ", ".join(requested_deliverables),
            "capability_route": plan.capability_route if plan is not None else "unsupported",
            "requested_capability": "registry-blocked request",
            "executed_capability": "not_executed",
            "performed_new_calculations": "false",
            "reused_existing_artifacts": "false",
            "resolved_target_ids_text": "No target IDs were resolved because execution did not start.",
            "honored_constraints_text": "No honored constraints were recorded because execution did not start.",
            "unmet_constraints_text": (
                "Execution was blocked before tool runtime because the Planner explicitly requested a microscopic action "
                "that is not represented in the current Amesp action registry: "
                + blocked_note
                + "."
            ),
            "missing_deliverables_text": (
                "; ".join(requested_deliverables)
                if requested_deliverables
                else "No deliverables were requested."
            ),
            "requested_route_summary": requested_route_summary,
            "task_completion_text": task_completion_text,
            "recent_context_note": "No additional microscopic runtime step was executed.",
            "capability_scope": self._capability_scope_text(),
            "structure_source_note": (
                "Execution was intentionally blocked before tool runtime because no registry-backed microscopic action "
                "matched the Planner request exactly."
            ),
            "unsupported_requests_note": self._unsupported_requests_note(unsupported_requests),
            "reasoning_summary_text": reasoning.reasoning_summary,
            "capability_limit_note": reasoning.capability_limit_note,
            "failure_policy": reasoning.failure_policy,
            "plan_steps": (
                "No execution steps were run because the Planner explicitly requested registry-unsupported microscopic "
                f"task(s): {blocked_note}."
            ),
            "expected_outputs_text": "No outputs were produced because tool execution did not start.",
            "result_summary_text": result_summary_text,
            "local_uncertainty_detail": (
                "the current Amesp registry does not expose the requested microscopic action, so no new local evidence "
                "was collected in this round"
            ),
        }
        rendered = self._prompts.render_sections("microscopic_amesp_specialized", render_payload)
        return AgentReport(
            agent_name="microscopic",
            task_received=task_received,
            task_completion_status="failed",
            completion_reason_code="action_not_supported_by_registry",
            task_completion=rendered["task_completion"],
            task_understanding=reasoning.task_understanding,
            reasoning_summary=rendered["reasoning_summary"],
            execution_plan=rendered["execution_plan"],
            result_summary=rendered["result_summary"],
            remaining_local_uncertainty=rendered["remaining_local_uncertainty"],
            tool_calls=["microscopic_reasoning(task_instruction_to_execution_plan)"],
            raw_results={
                "reasoning_output": reasoning.model_dump(mode="json"),
                "action_decision": action_decision.model_dump(mode="json"),
                "execution_plan_not_executed": plan.model_dump(mode="json") if plan is not None else None,
                "registry_blocked_requests": list(registry_blocked_requests),
            },
            structured_results={
                "backend": "amesp",
                "reasoning_backend": self._config.microscopic_backend,
                "task_mode": task_spec.mode,
                "task_label": task_spec.task_label,
                "task_objective": task_spec.objective,
                "task_completion_status": "failed",
                "completion_reason_code": "action_not_supported_by_registry",
                "task_completion": rendered["task_completion"],
                "reasoning": reasoning.model_dump(mode="json"),
                "reasoning_parse_mode": reasoning_parse_mode,
                "reasoning_contract_mode": reasoning_contract_mode,
                "reasoning_contract_errors": reasoning_contract_errors,
                "microscopic_action_status": action_decision.status,
                "unsupported_intent": blocked_note,
                "unsupported_parts": list(registry_blocked_requests),
                "closest_supported_actions": list(closest_supported_actions),
                "registry_action_name": None,
                "registry_validation_errors": registry_validation_errors,
                "registry_infeasible_for_verifier_handshake": True,
                "registry_infeasible_reason": "action_not_supported_by_registry",
                "execution_plan": plan.model_dump(mode="json") if plan is not None else None,
                "requested_capability": None,
                "executed_capability": None,
                "performed_new_calculations": False,
                "reused_existing_artifacts": False,
                "resolved_target_ids": {},
                "honored_constraints": [],
                "unmet_constraints": registry_validation_errors + list(plan.planning_unmet_constraints if plan is not None else []),
                "missing_deliverables": requested_deliverables,
                "error": {
                    "code": "action_not_supported_by_registry",
                    "message": result_summary_text,
                },
                "supported_scope": list(plan.supported_scope if plan is not None else []),
                "unsupported_requests": unsupported_requests,
                "artifact_bundle_id": None,
                "artifact_bundle_kind": None,
                "retry_without_new_capability": False,
            },
            generated_artifacts={},
            status="failed",
            planner_readable_report=rendered["planner_readable_report"],
        )
