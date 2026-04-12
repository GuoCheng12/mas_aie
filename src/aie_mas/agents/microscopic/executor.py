from __future__ import annotations

from typing import Any, Optional

from aie_mas.graph.state import (
    AgentFramingMode,
    AgentReport,
    CliActionSpec,
    MicroscopicTaskSpec,
    ReasoningPhase,
    SharedStructureContext,
    SharedStructureStatus,
)
from aie_mas.tools.amesp import AmespBaselineRunResult, AmespExecutionError
from aie_mas.tools.cli_execution import CliExecutionError, execute_cli_action, microscopic_command_id

from .compiler import MicroscopicReasoningParseError, normalize_reasoning_outcome_for_best_fit_translation
from .interpreter import MicroscopicReasoningOutcome


class MicroscopicExecutorMixin:
    def _build_cli_action(
        self,
        *,
        plan: Any,
        smiles: str,
        label: str,
        workdir: Any,
        available_artifacts: dict[str, Any],
        round_index: int,
        case_id: str,
        current_hypothesis: str,
    ) -> CliActionSpec:
        capability_name = plan.microscopic_tool_request.capability_name
        return CliActionSpec(
            command_id=microscopic_command_id(capability_name),
            command_program="python3",
            command_args=["-m", "aie_mas.cli.microscopic_exec"],
            stdin_payload={
                "tool_config": {
                    "amesp_bin": str(self._config.amesp_binary_path) if self._config.amesp_binary_path else None,
                    "npara": self._config.amesp_npara,
                    "maxcore_mb": self._config.amesp_maxcore_mb,
                    "use_ricosx": self._config.amesp_use_ricosx,
                    "s1_nstates": self._config.amesp_s1_nstates,
                    "td_tout": self._config.amesp_td_tout,
                    "follow_up_max_conformers": self._config.amesp_follow_up_max_conformers,
                    "follow_up_max_torsion_snapshots_total": self._config.amesp_follow_up_max_torsion_snapshots_total,
                    "probe_interval_seconds": self._config.amesp_probe_interval_seconds,
                },
                "plan": plan.model_dump(mode="json"),
                "smiles": smiles,
                "label": label,
                "workdir": str(workdir),
                "available_artifacts": available_artifacts,
                "round_index": round_index,
                "case_id": case_id,
                "current_hypothesis": current_hypothesis,
            },
            expected_outputs=list(plan.expected_outputs),
            perform_new_calculation=bool(plan.microscopic_tool_request.perform_new_calculation),
            reused_existing_artifacts=bool(plan.microscopic_tool_request.reuse_existing_artifacts_only),
            resolved_target_ids={},
            binding_mode=plan.binding_mode,
            requested_observable_tags=list(plan.requested_observable_tags),
        )

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

    def _rerun_reasoning_after_cli_failure(
        self,
        *,
        failure_context: dict[str, Any],
        current_hypothesis: str,
        reasoning_phase: ReasoningPhase,
        agent_framing_mode: AgentFramingMode,
        screening_focus_hypotheses: list[str],
        screening_focus_summary: Optional[str],
        task_received: str,
        task_spec: MicroscopicTaskSpec,
        recent_rounds_context: list[dict[str, object]],
        available_artifacts: dict[str, Any],
        shared_structure_context: Optional[SharedStructureContext],
        round_index: int,
        case_id: str,
    ) -> MicroscopicReasoningOutcome:
        self._emit_probe(
            round_index=round_index,
            case_id=case_id,
            current_hypothesis=current_hypothesis,
            stage="cli_repair_reasoning",
            status="start",
            details={"previous_cli_failure_context": failure_context},
        )
        reasoning_payload = self._build_reasoning_payload(
            current_hypothesis=current_hypothesis,
            reasoning_phase=reasoning_phase,
            agent_framing_mode=agent_framing_mode,
            screening_focus_hypotheses=screening_focus_hypotheses,
            screening_focus_summary=screening_focus_summary,
            task_instruction=task_received,
            task_spec=task_spec,
            recent_rounds_context=recent_rounds_context,
            available_artifacts=available_artifacts,
            shared_structure_context=shared_structure_context,
            round_index=round_index,
            previous_cli_failure_context=failure_context,
        )
        rendered_prompt = self._prompts.render("microscopic_reasoning", reasoning_payload)
        outcome = self._reasoning_backend.reason(rendered_prompt, reasoning_payload)
        outcome = normalize_reasoning_outcome_for_best_fit_translation(
            outcome,
            payload=reasoning_payload,
            config=self._config,
        )
        self._emit_probe(
            round_index=round_index,
            case_id=case_id,
            current_hypothesis=current_hypothesis,
            stage="cli_repair_reasoning",
            status="end",
            details={
                "task_understanding": outcome.reasoning_response.task_understanding,
                "reasoning_summary": outcome.reasoning_response.reasoning_summary,
                "reasoning_parse_mode": outcome.reasoning_parse_mode,
                "reasoning_contract_mode": outcome.reasoning_contract_mode,
                "reasoning_contract_errors": list(outcome.reasoning_contract_errors),
            },
        )
        return outcome

    def _repeated_no_new_observable_gain(
        self,
        *,
        recent_rounds_context: list[dict[str, object]],
        structured_results: dict[str, Any],
    ) -> bool:
        current_capability = str(structured_results.get("executed_capability") or "").strip()
        current_bundle = str(structured_results.get("artifact_bundle_id") or "").strip()
        current_requested = list(structured_results.get("requested_observable_tags") or [])
        current_covered = list(structured_results.get("covered_observable_tags") or [])
        current_residual = list(structured_results.get("residual_unmet_observable_tags") or [])
        if not current_capability or not current_bundle or not current_requested:
            return False
        matches = 0
        for entry in recent_rounds_context[-3:]:
            summaries = entry.get("agent_compact_summaries")
            if not isinstance(summaries, list):
                continue
            for summary in summaries:
                if not isinstance(summary, dict):
                    continue
                if str(summary.get("executed_capability") or "").strip() != current_capability:
                    continue
                refs = list(summary.get("artifact_references") or [])
                same_bundle = any(
                    isinstance(ref, dict) and str(ref.get("artifact_bundle_id") or "").strip() == current_bundle
                    for ref in refs
                )
                if not same_bundle:
                    continue
                if list(summary.get("requested_observable_tags") or []) != current_requested:
                    continue
                if list(summary.get("covered_observable_tags") or []) != current_covered:
                    continue
                if list(summary.get("residual_unmet_observable_tags") or []) != current_residual:
                    continue
                matches += 1
        return matches >= 2

    def run(
        self,
        smiles: str,
        task_received: str,
        task_spec: Optional[MicroscopicTaskSpec] = None,
        current_hypothesis: str = "unknown",
        *,
        reasoning_phase: ReasoningPhase = "portfolio_screening",
        agent_framing_mode: AgentFramingMode = "portfolio_neutral",
        screening_focus_hypotheses: Optional[list[str]] = None,
        screening_focus_summary: Optional[str] = None,
        recent_rounds_context: Optional[list[dict[str, object]]] = None,
        available_artifacts: Optional[dict[str, Any]] = None,
        shared_structure_context: Optional[SharedStructureContext] = None,
        shared_structure_status: SharedStructureStatus = "missing",
        allow_internal_structure_fallback: bool = True,
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
        screening_focus_hypotheses = screening_focus_hypotheses or []
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
            reasoning_phase=reasoning_phase,
            agent_framing_mode=agent_framing_mode,
            screening_focus_hypotheses=screening_focus_hypotheses,
            screening_focus_summary=screening_focus_summary,
            task_instruction=task_received,
            task_spec=task_spec,
            recent_rounds_context=recent_rounds_context,
            available_artifacts=available_artifacts,
            shared_structure_context=shared_structure_context,
            round_index=round_index,
        )
        rendered_prompt = self._prompts.render("microscopic_reasoning", reasoning_payload)
        try:
            outcome = self._reasoning_backend.reason(rendered_prompt, reasoning_payload)
        except MicroscopicReasoningParseError as exc:
            self._emit_probe(
                round_index=round_index,
                case_id=resolved_case_id,
                current_hypothesis=current_hypothesis,
                stage="reasoning",
                status="end",
                details={
                    "reasoning_backend": self._config.microscopic_backend,
                    "reasoning_parse_mode": "failed",
                    "reasoning_contract_mode": exc.contract_mode,
                    "reasoning_contract_errors": list(exc.contract_errors),
                },
            )
            return self._reasoning_parse_failure_report(
                task_received=task_received,
                task_spec=task_spec,
                current_hypothesis=current_hypothesis,
                reasoning_phase=reasoning_phase,
                agent_framing_mode=agent_framing_mode,
                screening_focus_hypotheses=screening_focus_hypotheses,
                screening_focus_summary=screening_focus_summary,
                parse_error=exc,
            )
        outcome = normalize_reasoning_outcome_for_best_fit_translation(
            outcome,
            payload=reasoning_payload,
            config=self._config,
        )
        reasoning = outcome.reasoning_response
        plan = outcome.compiled_execution_plan
        action_decision = outcome.action_decision
        reasoning_parse_mode = outcome.reasoning_parse_mode
        reasoning_contract_mode = outcome.reasoning_contract_mode
        reasoning_contract_errors = list(outcome.reasoning_contract_errors)
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
                "reasoning_parse_mode": reasoning_parse_mode,
                "reasoning_contract_mode": reasoning_contract_mode,
                "reasoning_contract_errors": reasoning_contract_errors,
            },
        )
        if plan is not None:
            self._emit_probe(
                round_index=round_index,
                case_id=resolved_case_id,
                current_hypothesis=current_hypothesis,
                stage="execution_plan",
                status="end",
                details=plan.model_dump(mode="json"),
            )
        else:
            self._emit_probe(
                round_index=round_index,
                case_id=resolved_case_id,
                current_hypothesis=current_hypothesis,
                stage="execution_plan",
                status="end",
                details={
                    "microscopic_action_status": action_decision.status,
                    "execution_action": action_decision.execution_action,
                    "discovery_actions": list(action_decision.discovery_actions),
                    "unsupported_parts": list(action_decision.unsupported_parts),
                },
            )
        registry_blocked_requests = self._registry_blocked_requests(task_received)
        if action_decision.status == "unsupported":
            return self._registry_blocked_request_report(
                task_received=task_received,
                task_spec=task_spec,
                current_hypothesis=current_hypothesis,
                reasoning_phase=reasoning_phase,
                agent_framing_mode=agent_framing_mode,
                screening_focus_hypotheses=screening_focus_hypotheses,
                screening_focus_summary=screening_focus_summary,
                outcome=outcome,
                registry_blocked_requests=list(action_decision.unsupported_parts),
            )
        if registry_blocked_requests:
            return self._registry_blocked_request_report(
                task_received=task_received,
                task_spec=task_spec,
                current_hypothesis=current_hypothesis,
                reasoning_phase=reasoning_phase,
                agent_framing_mode=agent_framing_mode,
                screening_focus_hypotheses=screening_focus_hypotheses,
                screening_focus_summary=screening_focus_summary,
                outcome=outcome,
                registry_blocked_requests=registry_blocked_requests,
            )

        if (
            self._amesp_tool is not None
            and not allow_internal_structure_fallback
            and shared_structure_context is None
            and not self._has_reusable_structure(available_artifacts)
        ):
            return self._shared_structure_unavailable_report(
                task_received=task_received,
                task_spec=task_spec,
                current_hypothesis=current_hypothesis,
                reasoning_phase=reasoning_phase,
                agent_framing_mode=agent_framing_mode,
                screening_focus_hypotheses=screening_focus_hypotheses,
                screening_focus_summary=screening_focus_summary,
                outcome=outcome,
                shared_structure_status=shared_structure_status,
            )

        if self._amesp_tool is not None:
            if plan is None:
                return self._reasoning_parse_failure_report(
                    task_received=task_received,
                    task_spec=task_spec,
                    current_hypothesis=current_hypothesis,
                    reasoning_phase=reasoning_phase,
                    agent_framing_mode=agent_framing_mode,
                    screening_focus_hypotheses=screening_focus_hypotheses,
                    screening_focus_summary=screening_focus_summary,
                    parse_error=MicroscopicReasoningParseError(
                        "Microscopic action decision did not compile into an execution plan.",
                        raw_text="",
                        contract_mode=reasoning_contract_mode,
                        contract_errors=["supported microscopic action decision did not produce an execution plan"],
                    ),
                )
            return self._run_real(
                smiles=smiles,
                task_received=task_received,
                task_spec=task_spec,
                current_hypothesis=current_hypothesis,
                reasoning_phase=reasoning_phase,
                agent_framing_mode=agent_framing_mode,
                screening_focus_hypotheses=screening_focus_hypotheses,
                screening_focus_summary=screening_focus_summary,
                outcome=outcome,
                recent_rounds_context=recent_rounds_context,
                available_artifacts=available_artifacts,
                shared_structure_context=shared_structure_context,
                case_id=resolved_case_id,
                round_index=round_index,
            )
        raise RuntimeError(
            "MicroscopicAgent requires an Amesp baseline tool; no alternate execution path is available."
        )

    def _run_real(
        self,
        *,
        smiles: str,
        task_received: str,
        task_spec: MicroscopicTaskSpec,
        current_hypothesis: str,
        reasoning_phase: ReasoningPhase,
        agent_framing_mode: AgentFramingMode,
        screening_focus_hypotheses: list[str],
        screening_focus_summary: Optional[str],
        outcome: MicroscopicReasoningOutcome,
        recent_rounds_context: list[dict[str, object]],
        available_artifacts: dict[str, Any],
        shared_structure_context: Optional[SharedStructureContext],
        case_id: str,
        round_index: int,
    ) -> AgentReport:
        current_outcome = outcome
        retry_history: list[dict[str, Any]] = []
        tool_calls: list[str] = []
        draft: dict[str, str] = {}
        for retry_index in range(self._config.cli_local_retry_attempts + 1):
            reasoning = current_outcome.reasoning_response
            plan = current_outcome.compiled_execution_plan
            action_decision = current_outcome.action_decision
            reasoning_parse_mode = current_outcome.reasoning_parse_mode
            reasoning_contract_mode = current_outcome.reasoning_contract_mode
            reasoning_contract_errors = list(current_outcome.reasoning_contract_errors)
            assert plan is not None

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
                "requested_focus": ", ".join(plan.requested_deliverables),
                "capability_route": plan.capability_route,
                "requested_capability": plan.microscopic_tool_request.capability_name,
                "executed_capability": plan.microscopic_tool_request.capability_name,
                "performed_new_calculations": str(plan.microscopic_tool_request.perform_new_calculation).lower(),
                "reused_existing_artifacts": str(plan.microscopic_tool_request.reuse_existing_artifacts_only).lower(),
                "resolved_target_ids_text": "No target IDs have been resolved yet.",
                "honored_constraints_text": "No honored constraints have been recorded yet.",
                "unmet_constraints_text": "No unmet constraints have been recorded yet.",
                "missing_deliverables_text": "No missing deliverables have been identified yet.",
                "requested_route_summary": plan.requested_route_summary,
                "task_completion_text": "Task completion is pending Amesp microscopic execution.",
                "recent_context_note": self._recent_context_note(recent_rounds_context),
                "capability_scope": self._capability_scope_text(),
                "structure_source_note": self._structure_source_note(
                    plan.structure_source,
                    available_artifacts,
                    shared_structure_context=shared_structure_context,
                ),
                "unsupported_requests_note": self._unsupported_requests_note(plan.unsupported_requests),
                "reasoning_summary_text": reasoning.reasoning_summary,
                "capability_limit_note": reasoning.capability_limit_note,
                "failure_policy": reasoning.failure_policy,
                "plan_steps": self._plan_steps_text(plan),
                "expected_outputs_text": ", ".join(plan.expected_outputs),
                "result_summary_text": "Amesp microscopic execution has not run yet.",
                "local_uncertainty_detail": self._remaining_uncertainty_text(
                    plan.unsupported_requests,
                    task_spec.mode,
                    plan.capability_route,
                    plan.microscopic_tool_request.capability_name,
                ),
                **self._translation_render_fields(action_decision=action_decision, plan=plan),
            }
            draft = self._prompts.render_sections("microscopic_amesp_specialized", render_payload)

            label = f"{case_id}_round_{round_index:02d}_micro"
            workdir = self._resolve_workdir(case_id=case_id, round_index=round_index)
            cli_action = self._build_cli_action(
                plan=plan,
                smiles=smiles,
                label=label,
                workdir=workdir,
                available_artifacts=available_artifacts,
                round_index=round_index,
                case_id=case_id,
                current_hypothesis=current_hypothesis,
            )
            reasoning.cli_action = cli_action
            reasoning.unsupported_requests = list(plan.unsupported_requests)
            tool_calls = [
                "microscopic_reasoning(task_instruction_to_execution_plan)",
                f"{cli_action.command_program} {' '.join(cli_action.command_args)}(command_id='{cli_action.command_id}', label='{label}')",
            ]
            if plan.structure_source == "existing_prepared_structure":
                tool_calls.insert(1, "shared_structure_context(reuse_prepared_3d_structure)")
            else:
                tool_calls.insert(1, "structure_preparation(smiles_to_3d or reusable prepared structure)")

            try:
                cli_result = execute_cli_action(
                    config=self._config,
                    action=cli_action,
                    expected_agent_name="microscopic",
                )
                run_result = AmespBaselineRunResult.model_validate(cli_result.parsed_json)
                structured_results = {
                    "backend": "amesp",
                    "reasoning_backend": self._config.microscopic_backend,
                    "task_mode": task_spec.mode,
                    "task_label": task_spec.task_label,
                    "task_objective": task_spec.objective,
                    "reasoning": reasoning.model_dump(mode="json"),
                    "reasoning_parse_mode": reasoning_parse_mode,
                    "reasoning_contract_mode": reasoning_contract_mode,
                    "reasoning_contract_errors": reasoning_contract_errors,
                    "microscopic_action_status": action_decision.status,
                    "unsupported_intent": None,
                    "unsupported_parts": list(action_decision.unsupported_parts),
                    "closest_supported_actions": [],
                    "registry_action_name": plan.microscopic_tool_request.capability_name,
                    "registry_validation_errors": [],
                    "command_id": cli_action.command_id,
                    "command_program": cli_action.command_program,
                    "command_args": list(cli_action.command_args),
                    "stdin_payload_summary": dict(cli_result.stdin_payload_summary),
                    "cli_exit_code": cli_result.cli_exit_code,
                    "cli_stdout_excerpt": cli_result.cli_stdout_excerpt,
                    "cli_stderr_excerpt": cli_result.cli_stderr_excerpt,
                    "cli_action": cli_action.model_dump(mode="json"),
                    "execution_plan": plan.model_dump(mode="json"),
                    "attempted_route": getattr(run_result, "route", plan.capability_route),
                    "requested_capability": plan.microscopic_tool_request.capability_name,
                    "executed_capability": cli_action.command_id,
                    "selected_capability": getattr(run_result, "executed_capability", plan.microscopic_tool_request.capability_name),
                    "performed_new_calculations": getattr(run_result, "performed_new_calculations", True),
                    "reused_existing_artifacts": getattr(run_result, "reused_existing_artifacts", False),
                    "resolved_target_ids": dict(getattr(run_result, "resolved_target_ids", {})),
                    "honored_constraints": list(getattr(run_result, "honored_constraints", [])),
                    "unmet_constraints": list(getattr(run_result, "unmet_constraints", [])),
                    "missing_deliverables": list(getattr(run_result, "missing_deliverables", [])),
                    "structure_source": plan.structure_source,
                    "supported_scope": plan.supported_scope,
                    "unsupported_requests": plan.unsupported_requests,
                    "structure": run_result.structure.model_dump(mode="json") if run_result.structure is not None else None,
                    "s0": run_result.s0.model_dump(mode="json") if run_result.s0 is not None else None,
                    "s1": run_result.s1.model_dump(mode="json") if run_result.s1 is not None else None,
                    "parsed_snapshot_records": list(getattr(run_result, "parsed_snapshot_records", [])),
                    "route_records": list(getattr(run_result, "route_records", [])),
                    "route_summary": dict(getattr(run_result, "route_summary", {})),
                    "vertical_state_manifold": self._vertical_state_manifold(run_result.s1) if run_result.s1 is not None else {},
                    "s0_energy": run_result.s0.final_energy_hartree if run_result.s0 is not None else None,
                    "s1_energy": (
                        run_result.s1.excited_states[0].total_energy_hartree
                        if run_result.s1 is not None and run_result.s1.excited_states
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
                    **self._translation_structured_fields(action_decision=action_decision, plan=plan),
                }
                raw_results = {
                    "reasoning_output": reasoning.model_dump(mode="json"),
                    "execution_plan": plan.model_dump(mode="json"),
                    "amesp_raw_step_results": run_result.raw_step_results,
                    "cli_command_result": cli_result.model_dump(mode="json"),
                }
                generated_artifacts = dict(run_result.generated_artifacts)
                generated_artifacts["source_round"] = round_index
                result_summary_text = self._successful_result_summary(structured_results)
                status = "success"
                break
            except CliExecutionError as exc:
                failure_context = self._cli_failure_context(
                    retry_index=retry_index,
                    action=cli_action,
                    error=exc,
                )
                retry_history.append(failure_context)
                if retry_index < self._config.cli_local_retry_attempts:
                    try:
                        current_outcome = self._rerun_reasoning_after_cli_failure(
                            failure_context=failure_context,
                            current_hypothesis=current_hypothesis,
                            reasoning_phase=reasoning_phase,
                            agent_framing_mode=agent_framing_mode,
                            screening_focus_hypotheses=screening_focus_hypotheses,
                            screening_focus_summary=screening_focus_summary,
                            task_received=task_received,
                            task_spec=task_spec,
                            recent_rounds_context=recent_rounds_context,
                            available_artifacts=available_artifacts,
                            shared_structure_context=shared_structure_context,
                            round_index=round_index,
                            case_id=case_id,
                        )
                    except MicroscopicReasoningParseError as retry_exc:
                        return self._reasoning_parse_failure_report(
                            task_received=task_received,
                            task_spec=task_spec,
                            current_hypothesis=current_hypothesis,
                            reasoning_phase=reasoning_phase,
                            agent_framing_mode=agent_framing_mode,
                            screening_focus_hypotheses=screening_focus_hypotheses,
                            screening_focus_summary=screening_focus_summary,
                            parse_error=retry_exc,
                        )
                    if current_outcome.action_decision.status == "unsupported":
                        return self._registry_blocked_request_report(
                            task_received=task_received,
                            task_spec=task_spec,
                            current_hypothesis=current_hypothesis,
                            reasoning_phase=reasoning_phase,
                            agent_framing_mode=agent_framing_mode,
                            screening_focus_hypotheses=screening_focus_hypotheses,
                            screening_focus_summary=screening_focus_summary,
                            outcome=current_outcome,
                            registry_blocked_requests=list(current_outcome.action_decision.unsupported_parts),
                        )
                    if current_outcome.compiled_execution_plan is None:
                        return self._reasoning_parse_failure_report(
                            task_received=task_received,
                            task_spec=task_spec,
                            current_hypothesis=current_hypothesis,
                            reasoning_phase=reasoning_phase,
                            agent_framing_mode=agent_framing_mode,
                            screening_focus_hypotheses=screening_focus_hypotheses,
                            screening_focus_summary=screening_focus_summary,
                            parse_error=MicroscopicReasoningParseError(
                                "Microscopic CLI self-repair did not produce an execution plan.",
                                raw_text="",
                                contract_mode=current_outcome.reasoning_contract_mode,
                                contract_errors=["cli self-repair produced no execution plan"],
                            ),
                        )
                    continue
                structured_results = {
                    "backend": "amesp",
                    "reasoning_backend": self._config.microscopic_backend,
                    "task_mode": task_spec.mode,
                    "task_label": task_spec.task_label,
                    "task_objective": task_spec.objective,
                    "reasoning": reasoning.model_dump(mode="json"),
                    "reasoning_parse_mode": reasoning_parse_mode,
                    "reasoning_contract_mode": reasoning_contract_mode,
                    "reasoning_contract_errors": reasoning_contract_errors,
                    "microscopic_action_status": action_decision.status,
                    "unsupported_intent": None,
                    "unsupported_parts": list(action_decision.unsupported_parts),
                    "closest_supported_actions": [],
                    "registry_action_name": plan.microscopic_tool_request.capability_name,
                    "registry_validation_errors": [],
                    "command_id": cli_action.command_id,
                    "command_program": cli_action.command_program,
                    "command_args": list(cli_action.command_args),
                    "stdin_payload_summary": dict(cli_action.stdin_payload),
                    "cli_exit_code": exc.exit_code,
                    "cli_stdout_excerpt": exc.stdout,
                    "cli_stderr_excerpt": exc.stderr,
                    "cli_action": cli_action.model_dump(mode="json"),
                    "execution_plan": plan.model_dump(mode="json"),
                    "attempted_route": plan.capability_route,
                    "requested_capability": plan.microscopic_tool_request.capability_name,
                    "executed_capability": cli_action.command_id,
                    "selected_capability": plan.microscopic_tool_request.capability_name,
                    "performed_new_calculations": bool(plan.microscopic_tool_request.perform_new_calculation),
                    "reused_existing_artifacts": bool(plan.microscopic_tool_request.reuse_existing_artifacts_only),
                    "resolved_target_ids": {},
                    "honored_constraints": [],
                    "unmet_constraints": [],
                    "missing_deliverables": list(plan.requested_deliverables),
                    "structure_source": plan.structure_source,
                    "supported_scope": plan.supported_scope,
                    "unsupported_requests": plan.unsupported_requests,
                    "error": {
                        "message": str(exc),
                        "stdout": exc.stdout,
                        "stderr": exc.stderr,
                    },
                    **self._translation_structured_fields(action_decision=action_decision, plan=plan),
                }
                raw_results = {
                    "reasoning_output": reasoning.model_dump(mode="json"),
                    "execution_plan": plan.model_dump(mode="json"),
                    "cli_command_result": {
                        "command_id": cli_action.command_id,
                        "command_program": cli_action.command_program,
                        "command_args": list(cli_action.command_args),
                        "stdin_payload_summary": dict(cli_action.stdin_payload),
                        "cli_exit_code": exc.exit_code,
                        "cli_stdout_excerpt": exc.stdout,
                        "cli_stderr_excerpt": exc.stderr,
                        "parsed_json": {},
                    },
                }
                generated_artifacts = {}
                result_summary_text = f"Microscopic CLI execution failed before a valid JSON result could be returned: {exc}"
                status = "failed"
                break
            except AmespExecutionError as exc:
                structured_results = {
                    "backend": "amesp",
                    "reasoning_backend": self._config.microscopic_backend,
                    "task_mode": task_spec.mode,
                    "task_label": task_spec.task_label,
                    "task_objective": task_spec.objective,
                    "reasoning": reasoning.model_dump(mode="json"),
                    "reasoning_parse_mode": reasoning_parse_mode,
                    "reasoning_contract_mode": reasoning_contract_mode,
                    "reasoning_contract_errors": reasoning_contract_errors,
                    "microscopic_action_status": action_decision.status,
                    "unsupported_intent": None,
                    "unsupported_parts": list(action_decision.unsupported_parts),
                    "closest_supported_actions": [],
                    "registry_action_name": plan.microscopic_tool_request.capability_name,
                    "registry_validation_errors": [],
                    "command_id": cli_action.command_id,
                    "command_program": cli_action.command_program,
                    "command_args": list(cli_action.command_args),
                    "stdin_payload_summary": dict(cli_action.stdin_payload),
                    "cli_action": cli_action.model_dump(mode="json"),
                    "execution_plan": plan.model_dump(mode="json"),
                    "attempted_route": plan.capability_route,
                    "requested_capability": plan.microscopic_tool_request.capability_name,
                    "executed_capability": cli_action.command_id,
                    "selected_capability": (
                        exc.structured_results.get("executed_capability")
                        if isinstance(exc.structured_results, dict)
                        else None
                    )
                    or plan.microscopic_tool_request.capability_name,
                    "performed_new_calculations": (
                        exc.structured_results.get("performed_new_calculations")
                        if isinstance(exc.structured_results, dict)
                        else plan.microscopic_tool_request.perform_new_calculation
                    ),
                    "reused_existing_artifacts": (
                        exc.structured_results.get("reused_existing_artifacts")
                        if isinstance(exc.structured_results, dict)
                        else plan.microscopic_tool_request.reuse_existing_artifacts_only
                    ),
                    "resolved_target_ids": (
                        dict(exc.structured_results.get("resolved_target_ids") or {})
                        if isinstance(exc.structured_results, dict)
                        else {}
                    ),
                    "honored_constraints": (
                        list(exc.structured_results.get("honored_constraints") or [])
                        if isinstance(exc.structured_results, dict)
                        else []
                    ),
                    "unmet_constraints": (
                        list(exc.structured_results.get("unmet_constraints") or [])
                        if isinstance(exc.structured_results, dict)
                        else []
                    ),
                    "missing_deliverables": [],
                    "structure_source": plan.structure_source,
                    "supported_scope": plan.supported_scope,
                    "unsupported_requests": plan.unsupported_requests,
                    "error": exc.to_payload(),
                    **self._translation_structured_fields(action_decision=action_decision, plan=plan),
                    **exc.structured_results,
                }
                raw_results = {
                    "reasoning_output": reasoning.model_dump(mode="json"),
                    "execution_plan": plan.model_dump(mode="json"),
                    "cli_command_result": {
                        "command_id": cli_action.command_id,
                        "command_program": cli_action.command_program,
                        "command_args": list(cli_action.command_args),
                        "stdin_payload_summary": dict(cli_action.stdin_payload),
                        "cli_exit_code": 0,
                        "cli_stdout_excerpt": "",
                        "cli_stderr_excerpt": "",
                        "parsed_json": {},
                    },
                    "amesp_error": exc.to_payload(),
                    **exc.raw_results,
                }
                generated_artifacts = dict(exc.generated_artifacts)
                generated_artifacts["source_round"] = round_index
                result_summary_text = self._failed_result_summary(exc)
                status = exc.status
                break

        structured_results["cli_retry_attempts_used"] = len(retry_history)
        structured_results["cli_retry_history"] = retry_history
        raw_results["cli_retry_history"] = retry_history

        structured_results["artifact_bundle_id"] = (
            generated_artifacts.get("artifact_bundle_id")
            or structured_results.get("artifact_bundle_id")
            or dict(structured_results.get("resolved_target_ids") or {}).get("artifact_bundle_id")
            or plan.microscopic_tool_request.artifact_bundle_id
        )
        structured_results["artifact_bundle_kind"] = (
            generated_artifacts.get("artifact_bundle_kind")
            or structured_results.get("artifact_bundle_kind")
            or plan.microscopic_tool_request.artifact_kind
        )

        structured_results["unmet_constraints"] = list(structured_results.get("unmet_constraints") or []) + list(
            plan.planning_unmet_constraints
        )

        task_completion_status, completion_reason_code, task_completion_text = self._task_completion_for_result(
            run_status=status,
            unsupported_requests=plan.unsupported_requests,
            task_mode=task_spec.mode,
            capability_route=plan.capability_route,
            requested_capability=plan.microscopic_tool_request.capability_name,
            planner_requested_capability=structured_results.get("planner_requested_capability"),
            executed_capability=structured_results.get("executed_capability"),
            fulfillment_mode=structured_results.get("fulfillment_mode"),
            translation_substituted_action=bool(structured_results.get("translation_substituted_action")),
            translation_substitution_reason=structured_results.get("translation_substitution_reason"),
            residual_unmet_observable_tags=list(structured_results.get("residual_unmet_observable_tags") or []),
            performed_new_calculations=bool(structured_results.get("performed_new_calculations")),
            reused_existing_artifacts=bool(structured_results.get("reused_existing_artifacts")),
            resolved_target_ids=dict(structured_results.get("resolved_target_ids") or {}),
            honored_constraints=list(structured_results.get("honored_constraints") or []),
            unmet_constraints=list(structured_results.get("unmet_constraints") or []),
            missing_deliverables=list(structured_results.get("missing_deliverables") or []),
            error_message=result_summary_text if status in {"partial", "failed"} else None,
            error_payload=structured_results.get("error"),
        )
        structured_results["task_completion_status"] = task_completion_status
        structured_results["completion_reason_code"] = completion_reason_code
        structured_results["task_completion"] = task_completion_text
        registry_handshake_reason = self._registry_handshake_reason(
            completion_reason_code=completion_reason_code,
            missing_deliverables=list(structured_results.get("missing_deliverables") or []),
            route_summary=(
                structured_results.get("route_summary")
                if isinstance(structured_results.get("route_summary"), dict)
                else None
            ),
            registry_validation_errors=list(structured_results.get("registry_validation_errors") or []),
        )
        structured_results["registry_infeasible_for_verifier_handshake"] = registry_handshake_reason is not None
        structured_results["registry_infeasible_reason"] = registry_handshake_reason
        if (
            bool(structured_results.get("reused_existing_artifacts"))
            and not bool(structured_results.get("performed_new_calculations"))
            and self._repeated_no_new_observable_gain(
                recent_rounds_context=recent_rounds_context,
                structured_results=structured_results,
            )
        ):
            structured_results["registry_infeasible_for_verifier_handshake"] = True
            structured_results["registry_infeasible_reason"] = "repeated_no_new_observable_gain"
            structured_results["retry_without_new_capability"] = False
            structured_results["unmet_constraints"] = list(structured_results.get("unmet_constraints") or []) + [
                "Repeated same-bundle parse-only route returned no new observable gain across recent rounds."
            ]
            task_completion_status, completion_reason_code, task_completion_text = self._task_completion_for_result(
                run_status=status,
                unsupported_requests=plan.unsupported_requests,
                task_mode=task_spec.mode,
                capability_route=plan.capability_route,
                requested_capability=plan.microscopic_tool_request.capability_name,
                planner_requested_capability=structured_results.get("planner_requested_capability"),
                executed_capability=structured_results.get("executed_capability"),
                fulfillment_mode=structured_results.get("fulfillment_mode"),
                translation_substituted_action=bool(structured_results.get("translation_substituted_action")),
                translation_substitution_reason=structured_results.get("translation_substitution_reason"),
                residual_unmet_observable_tags=list(structured_results.get("residual_unmet_observable_tags") or []),
                performed_new_calculations=bool(structured_results.get("performed_new_calculations")),
                reused_existing_artifacts=bool(structured_results.get("reused_existing_artifacts")),
                resolved_target_ids=dict(structured_results.get("resolved_target_ids") or {}),
                honored_constraints=list(structured_results.get("honored_constraints") or []),
                unmet_constraints=list(structured_results.get("unmet_constraints") or []),
                missing_deliverables=list(structured_results.get("missing_deliverables") or []),
                error_message=result_summary_text if status in {"partial", "failed"} else None,
                error_payload=structured_results.get("error"),
            )
            structured_results["task_completion_status"] = task_completion_status
            structured_results["completion_reason_code"] = completion_reason_code
            structured_results["task_completion"] = task_completion_text

        rendered = self._prompts.render_sections(
            "microscopic_amesp_specialized",
            {
                **render_payload,
                "task_completion_text": task_completion_text,
                "executed_capability": structured_results.get("executed_capability") or plan.microscopic_tool_request.capability_name,
                "performed_new_calculations": str(bool(structured_results.get("performed_new_calculations"))).lower(),
                "reused_existing_artifacts": str(bool(structured_results.get("reused_existing_artifacts"))).lower(),
                "resolved_target_ids_text": self._resolved_target_ids_text(
                    dict(structured_results.get("resolved_target_ids") or {})
                ),
                "honored_constraints_text": self._constraint_text(
                    list(structured_results.get("honored_constraints") or []),
                    default_text="No honored constraints were recorded.",
                ),
                "unmet_constraints_text": self._constraint_text(
                    list(structured_results.get("unmet_constraints") or []),
                    default_text="No unmet constraints were recorded.",
                ),
                "missing_deliverables_text": self._missing_deliverables_text(
                    list(structured_results.get("missing_deliverables") or [])
                ),
                "result_summary_text": result_summary_text,
            },
        )

        return AgentReport(
            agent_name="microscopic",
            task_received=task_received,
            task_completion_status=task_completion_status,  # type: ignore[arg-type]
            completion_reason_code=completion_reason_code,  # type: ignore[arg-type]
            task_completion=rendered["task_completion"],
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
