from __future__ import annotations

from collections import Counter
from typing import Any

from aie_mas.graph.state import (
    AieMasState,
    EvidenceFamily,
    PlannerArtifactReference,
    PlannerContextRoundSummary,
    WorkingMemoryAgentEntry,
    WorkingMemoryEntry,
)


_MICROSCOPIC_ACTION_LABELS: tuple[str, ...] = (
    "list_rotatable_dihedrals",
    "list_available_conformers",
    "list_artifact_bundles",
    "list_artifact_bundle_members",
    "run_baseline_bundle",
    "run_conformer_bundle",
    "run_torsion_snapshots",
    "run_targeted_charge_analysis",
    "run_targeted_localized_orbital_analysis",
    "run_targeted_natural_orbital_analysis",
    "run_targeted_density_population_analysis",
    "run_targeted_transition_dipole_analysis",
    "run_targeted_approx_delta_dipole_analysis",
    "run_ris_state_characterization",
    "parse_snapshot_outputs",
    "extract_ct_descriptors_from_bundle",
    "extract_geometry_descriptors_from_bundle",
    "inspect_raw_artifact_bundle",
    "run_targeted_state_characterization",
    "unsupported_excited_state_relaxation",
)
_EVIDENCE_FAMILY_BY_ACTION: dict[str, tuple[EvidenceFamily, ...]] = {
    "run_torsion_snapshots": ("torsion_sensitivity",),
    "parse_snapshot_outputs": ("torsion_sensitivity",),
    "run_baseline_bundle": ("state_ordering_brightness",),
    "run_targeted_state_characterization": ("state_ordering_brightness",),
    "run_targeted_transition_dipole_analysis": ("state_ordering_brightness",),
    "run_ris_state_characterization": ("state_ordering_brightness",),
    "run_targeted_charge_analysis": ("charge_localization",),
    "run_targeted_approx_delta_dipole_analysis": ("charge_localization",),
    "run_targeted_density_population_analysis": ("charge_localization",),
    "run_targeted_localized_orbital_analysis": ("charge_localization",),
    "run_targeted_natural_orbital_analysis": ("charge_localization",),
    "extract_ct_descriptors_from_bundle": ("charge_localization",),
    "extract_geometry_descriptors_from_bundle": ("geometry_precondition",),
    "inspect_raw_artifact_bundle": ("raw_artifact_inspection",),
    "verifier": ("external_precedent",),
}


class WorkingMemoryManager:
    def append_round_summary(self, state: AieMasState) -> AieMasState:
        if state.last_planner_decision is None:
            raise ValueError("Planner decision is required before updating working memory.")

        action_taken = ", ".join(report.agent_name for report in state.active_round_reports)
        if not action_taken:
            action_taken = state.last_planner_decision.action

        evidence_summary = " | ".join(
            f"{report.agent_name}: {self._compact_report_observation(report)}" for report in state.active_round_reports
        )
        if not evidence_summary:
            evidence_summary = state.latest_evidence_summary or "No agent evidence was recorded."

        diagnosis_summary = state.last_planner_decision.diagnosis
        if len(diagnosis_summary) > 240:
            diagnosis_summary = f"{diagnosis_summary[:237]}..."

        agent_reports = [
            WorkingMemoryAgentEntry(
                agent_name=report.agent_name,
                task_received=report.task_received,
                task_completion_status=report.task_completion_status,
                completion_reason_code=report.completion_reason_code,
                task_completion=report.task_completion,
                task_understanding=report.task_understanding,
                reasoning_summary=report.reasoning_summary,
                execution_plan=report.execution_plan,
                result_summary=report.result_summary,
                remaining_local_uncertainty=report.remaining_local_uncertainty,
                generated_artifacts=self._compact_generated_artifacts(report),
                planner_compact_summary=self._planner_compact_summary(report),
                status=report.status,
            )
            for report in state.active_round_reports
        ]
        local_uncertainty_summary = " | ".join(
            f"{report.agent_name}: {report.remaining_local_uncertainty}" for report in state.active_round_reports
        )
        if not local_uncertainty_summary:
            local_uncertainty_summary = None
        repeated_local_uncertainty_signals = self._repeated_local_uncertainties(state, agent_reports)
        planned_action_label = self._planned_action_label(state)
        executed_action_labels = self._executed_action_labels(state.active_round_reports)
        executed_evidence_families = self._executed_evidence_families(executed_action_labels)
        planner_task_instruction = self._backfilled_task_instruction(
            planner_task_instruction=state.last_planner_decision.task_instruction,
            planner_agent_task_instructions=state.last_planner_decision.agent_task_instructions,
            planned_action_label=planned_action_label,
            executed_action_labels=executed_action_labels,
        )

        entry = WorkingMemoryEntry(
            round_id=state.round_idx + 1,
            current_hypothesis=state.current_hypothesis or "unknown",
            confidence=state.confidence or 0.0,
            hypothesis_pool=list(state.hypothesis_pool),
            reasoning_phase=state.last_planner_decision.reasoning_phase,
            agent_framing_mode=state.last_planner_decision.agent_framing_mode,
            portfolio_screening_complete=state.last_planner_decision.portfolio_screening_complete,
            coverage_debt_hypotheses=list(state.last_planner_decision.coverage_debt_hypotheses),
            credible_alternative_hypotheses=list(state.last_planner_decision.credible_alternative_hypotheses),
            hypothesis_screening_ledger=list(state.last_planner_decision.hypothesis_screening_ledger),
            portfolio_screening_summary=state.last_planner_decision.portfolio_screening_summary,
            screening_focus_hypotheses=list(state.last_planner_decision.screening_focus_hypotheses),
            screening_focus_summary=state.last_planner_decision.screening_focus_summary,
            runner_up_hypothesis=state.runner_up_hypothesis,
            runner_up_confidence=state.runner_up_confidence,
            action_taken=action_taken,
            evidence_summary=evidence_summary,
            diagnosis_summary=diagnosis_summary,
            main_gap=state.latest_main_gap or "Not specified.",
            conflict_status=state.latest_conflict_status or "unknown",
            next_action=state.last_planner_decision.action,
            planner_task_instruction=planner_task_instruction,
            planner_agent_task_instructions=dict(state.last_planner_decision.agent_task_instructions),
            hypothesis_uncertainty_note=state.last_planner_decision.hypothesis_uncertainty_note,
            final_hypothesis_rationale=state.last_planner_decision.final_hypothesis_rationale,
            capability_assessment=state.last_planner_decision.capability_assessment,
            stagnation_assessment=state.last_planner_decision.stagnation_assessment,
            contraction_reason=state.last_planner_decision.contraction_reason,
            information_gain_assessment=state.last_planner_decision.information_gain_assessment,
            gap_trend=state.last_planner_decision.gap_trend,
            stagnation_detected=state.last_planner_decision.stagnation_detected,
            hypothesis_reweight_explanation=dict(state.last_planner_decision.hypothesis_reweight_explanation),
            decision_pair=list(state.last_planner_decision.decision_pair),
            decision_gate_status=state.last_planner_decision.decision_gate_status,
            verifier_supplement_target_pair=state.last_planner_decision.verifier_supplement_target_pair,
            verifier_supplement_status=state.last_planner_decision.verifier_supplement_status,
            verifier_information_gain=state.last_planner_decision.verifier_information_gain,
            verifier_evidence_relation=state.last_planner_decision.verifier_evidence_relation,
            verifier_supplement_summary=state.last_planner_decision.verifier_supplement_summary,
            closure_justification_target_pair=state.last_planner_decision.closure_justification_target_pair,
            closure_justification_status=state.last_planner_decision.closure_justification_status,
            closure_justification_evidence_source=state.last_planner_decision.closure_justification_evidence_source,
            closure_justification_basis=state.last_planner_decision.closure_justification_basis,
            closure_justification_summary=state.last_planner_decision.closure_justification_summary,
            pairwise_task_agent=state.last_planner_decision.pairwise_task_agent,
            pairwise_task_completed_for_pair=state.last_planner_decision.pairwise_task_completed_for_pair,
            pairwise_task_outcome=state.last_planner_decision.pairwise_task_outcome,
            pairwise_task_rationale=state.last_planner_decision.pairwise_task_rationale,
            pairwise_resolution_mode=state.last_planner_decision.pairwise_resolution_mode,
            pairwise_resolution_evidence_sources=list(
                state.last_planner_decision.pairwise_resolution_evidence_sources
            ),
            pairwise_resolution_summary=state.last_planner_decision.pairwise_resolution_summary,
            finalization_mode=state.last_planner_decision.finalization_mode,
            pairwise_verifier_completed_for_pair=state.last_planner_decision.pairwise_verifier_completed_for_pair,
            pairwise_verifier_evidence_specificity=state.last_planner_decision.pairwise_verifier_evidence_specificity,
            planned_action_label=planned_action_label,
            executed_action_labels=executed_action_labels,
            executed_evidence_families=executed_evidence_families,
            planner_context_budget_status=state.last_planner_decision.planner_context_budget_status,
            planner_context_compaction_level=state.last_planner_decision.planner_context_compaction_level,
            planner_context_estimated_tokens=state.last_planner_decision.planner_context_estimated_tokens,
            local_uncertainty_summary=local_uncertainty_summary,
            repeated_local_uncertainty_signals=repeated_local_uncertainty_signals,
            capability_lesson_candidates=list(state.last_planner_decision.capability_lesson_candidates),
            agent_reports=agent_reports,
        )
        state.working_memory.append(entry)
        state.planned_action_label = planned_action_label
        state.executed_action_labels = executed_action_labels
        state.executed_evidence_families = executed_evidence_families
        state.planner_context_budget_status = state.last_planner_decision.planner_context_budget_status
        state.planner_context_compaction_level = state.last_planner_decision.planner_context_compaction_level
        state.planner_context_estimated_tokens = state.last_planner_decision.planner_context_estimated_tokens
        state.round_idx += 1
        state.active_round_reports.clear()
        return state

    def build_recent_rounds_context(
        self,
        state: AieMasState,
        *,
        window_size: int = 3,
    ) -> list[dict[str, object]]:
        recent_entries = state.working_memory[-window_size:]
        context: list[dict[str, object]] = []
        for entry in recent_entries:
            context.append(
                {
                    "round_id": entry.round_id,
                    "current_hypothesis": entry.current_hypothesis,
                    "confidence": entry.confidence,
                    "reasoning_phase": entry.reasoning_phase,
                    "agent_framing_mode": entry.agent_framing_mode,
                    "portfolio_screening_complete": entry.portfolio_screening_complete,
                    "coverage_debt_hypotheses": list(entry.coverage_debt_hypotheses),
                    "credible_alternative_hypotheses": list(entry.credible_alternative_hypotheses),
                    "hypothesis_screening_ledger": [
                        record.model_dump(mode="json") for record in entry.hypothesis_screening_ledger
                    ],
                    "portfolio_screening_summary": self._truncate(entry.portfolio_screening_summary or "", 220),
                    "screening_focus_hypotheses": list(entry.screening_focus_hypotheses),
                    "screening_focus_summary": self._truncate(entry.screening_focus_summary or "", 220),
                    "runner_up_hypothesis": entry.runner_up_hypothesis,
                    "runner_up_confidence": entry.runner_up_confidence,
                    "action_taken": entry.action_taken,
                    "main_gap": entry.main_gap,
                    "decision_pair": list(entry.decision_pair),
                    "decision_gate_status": entry.decision_gate_status,
                    "verifier_supplement_target_pair": entry.verifier_supplement_target_pair,
                    "verifier_supplement_status": entry.verifier_supplement_status,
                    "verifier_information_gain": entry.verifier_information_gain,
                    "verifier_evidence_relation": entry.verifier_evidence_relation,
                    "verifier_supplement_summary": self._truncate(entry.verifier_supplement_summary or "", 220),
                    "closure_justification_target_pair": entry.closure_justification_target_pair,
                    "closure_justification_status": entry.closure_justification_status,
                    "closure_justification_evidence_source": entry.closure_justification_evidence_source,
                    "closure_justification_basis": entry.closure_justification_basis,
                    "closure_justification_summary": self._truncate(
                        entry.closure_justification_summary or "",
                        220,
                    ),
                    "pairwise_task_agent": entry.pairwise_task_agent,
                    "pairwise_task_completed_for_pair": entry.pairwise_task_completed_for_pair,
                    "pairwise_task_outcome": entry.pairwise_task_outcome,
                    "pairwise_task_rationale": self._truncate(entry.pairwise_task_rationale or "", 220),
                    "pairwise_resolution_mode": entry.pairwise_resolution_mode,
                    "pairwise_resolution_evidence_sources": list(entry.pairwise_resolution_evidence_sources),
                    "pairwise_resolution_summary": self._truncate(entry.pairwise_resolution_summary or "", 220),
                    "finalization_mode": entry.finalization_mode,
                    "pairwise_verifier_completed_for_pair": entry.pairwise_verifier_completed_for_pair,
                    "pairwise_verifier_evidence_specificity": entry.pairwise_verifier_evidence_specificity,
                    "evidence_summary": self._truncate(entry.evidence_summary, 260),
                    "diagnosis_summary": self._truncate(entry.diagnosis_summary, 260),
                    "planner_task_instruction": self._truncate(entry.planner_task_instruction or "", 220),
                    "planned_action_label": entry.planned_action_label,
                    "executed_action_labels": list(entry.executed_action_labels),
                    "executed_evidence_families": list(entry.executed_evidence_families),
                    "planner_context_budget_status": entry.planner_context_budget_status,
                    "planner_context_compaction_level": entry.planner_context_compaction_level,
                    "planner_context_estimated_tokens": entry.planner_context_estimated_tokens,
                    "local_uncertainty_summary": self._truncate(entry.local_uncertainty_summary or "", 260),
                    "repeated_local_uncertainty_signals": entry.repeated_local_uncertainty_signals,
                    "capability_assessment": self._truncate(entry.capability_assessment or "", 220),
                    "stagnation_assessment": self._truncate(entry.stagnation_assessment or "", 220),
                    "contraction_reason": self._truncate(entry.contraction_reason or "", 220),
                    "information_gain_assessment": self._truncate(
                        entry.information_gain_assessment or "",
                        220,
                    ),
                    "gap_trend": entry.gap_trend,
                    "stagnation_detected": entry.stagnation_detected,
                    "agent_compact_summaries": [
                        {
                            "agent_name": agent_report.agent_name,
                            "status": agent_report.status,
                            "task_completion_status": agent_report.task_completion_status,
                            **dict(agent_report.planner_compact_summary),
                        }
                        for agent_report in entry.agent_reports
                    ],
                }
            )
        return context

    def build_planner_context_projection(
        self,
        state: AieMasState,
        *,
        recent_window: int = 5,
        history_window: int | None = None,
        latest_detail: str = "standard",
    ) -> dict[str, object]:
        entries = state.working_memory[-history_window:] if history_window is not None else state.working_memory
        working_memory_summary = self._compact_working_memory_summary(entries)
        projection: dict[str, object] = {
            "working_memory_summary": [item.model_dump(mode="json") for item in working_memory_summary],
            "recent_rounds_context": self.build_recent_rounds_context(state, window_size=recent_window),
            "recent_capability_context": self.build_capability_context(state),
            "latest_macro_report": self._compact_agent_report_for_planner(
                state.macro_reports[-1] if state.macro_reports else None,
                detail_level=latest_detail,
            ),
            "latest_microscopic_report": self._compact_agent_report_for_planner(
                state.microscopic_reports[-1] if state.microscopic_reports else None,
                detail_level=latest_detail,
            ),
            "latest_verifier_report": self._compact_agent_report_for_planner(
                state.verifier_reports[-1] if state.verifier_reports else None,
                detail_level=latest_detail,
            ),
        }
        if state.verifier_reports:
            projection["verifier_report"] = projection["latest_verifier_report"]
        return projection

    def build_capability_context(
        self,
        state: AieMasState,
        *,
        window_size: int = 3,
    ) -> dict[str, object]:
        recent_entries = state.working_memory[-window_size:]
        repeated_gaps = self._repeated_strings([entry.main_gap for entry in recent_entries if entry.main_gap])
        repeated_uncertainties = self._repeated_strings(
            [
                agent_report.remaining_local_uncertainty
                for entry in recent_entries
                for agent_report in entry.agent_reports
                if agent_report.remaining_local_uncertainty
            ]
        )
        repeated_actions = self._repeated_strings(
            [entry.action_taken for entry in recent_entries if entry.action_taken]
        )
        low_information_round_ids = [
            entry.round_id
            for entry in recent_entries
            if entry.information_gain_assessment
            and any(
                marker in entry.information_gain_assessment.lower()
                for marker in ("limited", "little", "modest", "not shrinking")
            )
        ]
        stagnation_round_ids = [entry.round_id for entry in recent_entries if entry.stagnation_detected]
        return {
            "recent_round_count": len(recent_entries),
            "repeated_main_gaps": repeated_gaps,
            "repeated_actions": repeated_actions,
            "repeated_local_uncertainties": repeated_uncertainties,
            "recent_executed_evidence_families": list(
                dict.fromkeys(
                    family
                    for entry in recent_entries
                    for family in entry.executed_evidence_families
                )
            ),
            "low_information_round_ids": low_information_round_ids,
            "stagnation_round_ids": stagnation_round_ids,
        }

    def _compact_working_memory_summary(
        self,
        entries: list[WorkingMemoryEntry],
    ) -> list[PlannerContextRoundSummary]:
        summaries: list[PlannerContextRoundSummary] = []
        previous_entry: WorkingMemoryEntry | None = None
        for entry in entries:
            artifact_references = self._round_artifact_references(entry)
            key_observations = self._round_key_observations(entry)
            key_missing_deliverables = self._round_missing_deliverables(entry)
            summaries.append(
                PlannerContextRoundSummary(
                    round=entry.round_id,
                    selected_next_action=entry.next_action,
                    planned_action_label=entry.planned_action_label,
                    executed_action_labels=list(entry.executed_action_labels),
                    task_instruction=self._truncate(entry.planner_task_instruction or "", 180) or None,
                    status=self._round_status(entry),
                    key_observations=key_observations,
                    key_missing_deliverables=key_missing_deliverables,
                    evidence_families_covered=list(entry.executed_evidence_families),
                    artifact_references=artifact_references,
                    coverage_debt_delta=self._coverage_debt_delta(previous_entry, entry),
                    hypothesis_delta=self._hypothesis_delta(previous_entry, entry),
                )
            )
            previous_entry = entry
        return summaries

    def _compact_agent_report_for_planner(
        self,
        report: Any,
        *,
        detail_level: str = "standard",
    ) -> dict[str, object] | None:
        if report is None:
            return None
        agent_name = getattr(report, "agent_name", "")
        compact_summary = self._planner_compact_summary(report)
        payload: dict[str, object] = {
            "agent_name": agent_name,
            "status": getattr(report, "status", "unknown"),
            "task_completion_status": getattr(report, "task_completion_status", "unknown"),
            "completion_reason_code": getattr(report, "completion_reason_code", None),
            "task_received": self._truncate(str(getattr(report, "task_received", "") or ""), 220),
            "task_completion": self._truncate(str(getattr(report, "task_completion", "") or ""), 220),
            "task_understanding": self._truncate(str(getattr(report, "task_understanding", "") or ""), 220),
            "reasoning_summary": self._truncate(str(getattr(report, "reasoning_summary", "") or ""), 220),
            "execution_plan": self._truncate(str(getattr(report, "execution_plan", "") or ""), 220),
            "result_summary": self._truncate(str(getattr(report, "result_summary", "") or ""), 260),
            "remaining_local_uncertainty": self._truncate(
                str(getattr(report, "remaining_local_uncertainty", "") or ""),
                220,
            ),
            "planner_compact_summary": compact_summary,
        }
        structured_results = getattr(report, "structured_results", {}) or {}
        if isinstance(structured_results, dict):
            payload["structured_results"] = {
                "status": structured_results.get("status"),
                "requested_capability": structured_results.get("requested_capability"),
                "executed_capability": structured_results.get("executed_capability"),
                "performed_new_calculations": structured_results.get("performed_new_calculations"),
                "reused_existing_artifacts": structured_results.get("reused_existing_artifacts"),
                "fulfillment_mode": structured_results.get("fulfillment_mode"),
                "binding_mode": structured_results.get("binding_mode"),
                "planner_requested_capability": structured_results.get("planner_requested_capability"),
                "translation_substituted_action": structured_results.get("translation_substituted_action"),
                "translation_substitution_reason": self._truncate(
                    str(structured_results.get("translation_substitution_reason") or ""),
                    220,
                ),
                "requested_observable_tags": list(structured_results.get("requested_observable_tags") or []),
                "covered_observable_tags": list(structured_results.get("covered_observable_tags") or []),
                "residual_unmet_observable_tags": list(
                    structured_results.get("residual_unmet_observable_tags") or []
                ),
                "resolved_target_ids": dict(structured_results.get("resolved_target_ids") or {}),
                "honored_constraints": list(structured_results.get("honored_constraints") or []),
                "unmet_constraints": list(structured_results.get("unmet_constraints") or []),
                "missing_deliverables": list(structured_results.get("missing_deliverables") or []),
                "artifact_bundle_id": structured_results.get("artifact_bundle_id"),
                "artifact_bundle_kind": structured_results.get("artifact_bundle_kind"),
                "registry_infeasible_reason": structured_results.get("registry_infeasible_reason"),
                "error": self._compact_error_payload(structured_results.get("error")),
                "verifier_target_pair": structured_results.get("verifier_target_pair"),
                "pairwise_verifier_completed_for_pair": structured_results.get("pairwise_verifier_completed_for_pair"),
                "pairwise_verifier_evidence_specificity": structured_results.get(
                    "pairwise_verifier_evidence_specificity"
                ),
                "source_count": structured_results.get("source_count"),
                "topic_summary": structured_results.get("topic_summary"),
                "verifier_supplement_status": structured_results.get("verifier_supplement_status"),
                "verifier_information_gain": structured_results.get("verifier_information_gain"),
                "verifier_evidence_relation": structured_results.get("verifier_evidence_relation"),
                "verifier_supplement_summary": self._truncate(
                    str(structured_results.get("verifier_supplement_summary") or ""),
                    220,
                ),
            }
        if detail_level == "standard":
            payload["generated_artifacts"] = self._compact_generated_artifacts(report)
            payload["planner_readable_report"] = self._truncate(
                str(getattr(report, "planner_readable_report", "") or ""),
                260,
            )
        elif detail_level == "compact":
            payload["generated_artifacts"] = self._compact_generated_artifacts(report)
        return payload

    def _compact_error_payload(self, error_payload: Any) -> dict[str, object]:
        if error_payload is None:
            return {}
        if isinstance(error_payload, dict):
            compact_error: dict[str, object] = {}
            code = error_payload.get("code")
            if code is not None:
                compact_error["code"] = str(code)
            message = error_payload.get("message")
            if message is not None:
                compact_error["message"] = self._truncate(str(message), 220)
            for key in ("type", "status", "stage"):
                value = error_payload.get(key)
                if value is not None:
                    compact_error[key] = str(value)
            if compact_error:
                return compact_error
        return {"message": self._truncate(str(error_payload), 220)}

    def _planner_compact_summary(self, report: Any) -> dict[str, object]:
        structured_results = getattr(report, "structured_results", {}) or {}
        executed_capability = str(structured_results.get("executed_capability") or "").strip()
        observations: list[str] = []
        if executed_capability:
            observations.append(f"executed_capability={executed_capability}")
        fulfillment_mode = str(structured_results.get("fulfillment_mode") or "").strip()
        if fulfillment_mode:
            observations.append(f"fulfillment_mode={fulfillment_mode}")
        if structured_results.get("translation_substituted_action"):
            substitution_reason = self._truncate(
                str(structured_results.get("translation_substitution_reason") or ""),
                140,
            )
            observations.append(
                substitution_reason or "translation_substituted_action=true"
            )
        result_summary = self._truncate(str(getattr(report, "result_summary", "") or ""), 180)
        if result_summary:
            observations.append(result_summary)
        route_summary = structured_results.get("route_summary")
        if isinstance(route_summary, dict):
            route_label = str(route_summary.get("summary") or route_summary.get("route_observation") or "").strip()
            if route_label:
                observations.append(self._truncate(route_label, 160))
        return {
            "executed_capability": executed_capability or None,
            "fulfillment_mode": fulfillment_mode or None,
            "planner_requested_capability": structured_results.get("planner_requested_capability"),
            "translation_substituted_action": bool(structured_results.get("translation_substituted_action")),
            "covered_observable_tags": list(structured_results.get("covered_observable_tags") or []),
            "residual_unmet_observable_tags": list(
                structured_results.get("residual_unmet_observable_tags") or []
            ),
            "key_observations": observations[:3],
            "key_missing_deliverables": list(structured_results.get("missing_deliverables") or []),
            "artifact_references": [
                item.model_dump(mode="json")
                for item in self._artifact_references_from_report(report)
            ],
        }

    def _compact_generated_artifacts(self, report: Any) -> dict[str, object]:
        structured_results = getattr(report, "structured_results", {}) or {}
        generated_artifacts = getattr(report, "generated_artifacts", {}) or {}
        artifact_references = self._artifact_references_from_report(report)
        compact: dict[str, object] = {}
        if artifact_references:
            compact["artifact_references"] = [item.model_dump(mode="json") for item in artifact_references]
        if generated_artifacts.get("source_bundle_id") is not None:
            compact["source_bundle_id"] = generated_artifacts.get("source_bundle_id")
        if generated_artifacts.get("source_member_ids") is not None:
            compact["source_member_ids"] = list(generated_artifacts.get("source_member_ids") or [])
        if structured_results.get("resolved_target_ids") is not None:
            compact["resolved_target_ids"] = dict(structured_results.get("resolved_target_ids") or {})
        return compact

    def _artifact_references_from_report(self, report: Any) -> list[PlannerArtifactReference]:
        structured_results = getattr(report, "structured_results", {}) or {}
        generated_artifacts = getattr(report, "generated_artifacts", {}) or {}
        references_by_id: dict[str, PlannerArtifactReference] = {}

        def _record(
            *,
            artifact_bundle_id: str | None,
            artifact_kind: str | None = None,
            selected_member_ids: list[str] | None = None,
            source_capability: str | None = None,
            parse_capabilities_supported: list[str] | None = None,
        ) -> None:
            bundle_id = str(artifact_bundle_id or "").strip()
            if not bundle_id:
                return
            existing = references_by_id.get(bundle_id)
            merged_member_ids = list(dict.fromkeys(selected_member_ids or []))
            merged_parse_caps = list(dict.fromkeys(parse_capabilities_supported or []))
            if existing is None:
                references_by_id[bundle_id] = PlannerArtifactReference(
                    artifact_bundle_id=bundle_id,
                    artifact_kind=artifact_kind if artifact_kind else None,
                    selected_member_ids=merged_member_ids,
                    source_capability=source_capability if source_capability else None,
                    parse_capabilities_supported=merged_parse_caps,
                )
                return
            if merged_member_ids:
                existing.selected_member_ids = list(
                    dict.fromkeys([*existing.selected_member_ids, *merged_member_ids])
                )
            if merged_parse_caps:
                existing.parse_capabilities_supported = list(
                    dict.fromkeys([*existing.parse_capabilities_supported, *merged_parse_caps])
                )
            if not existing.artifact_kind and artifact_kind:
                existing.artifact_kind = artifact_kind
            if not existing.source_capability and source_capability:
                existing.source_capability = source_capability

        _record(
            artifact_bundle_id=structured_results.get("artifact_bundle_id"),
            artifact_kind=structured_results.get("artifact_bundle_kind"),
            selected_member_ids=list(generated_artifacts.get("source_member_ids") or []),
            source_capability=structured_results.get("executed_capability"),
        )
        for entry in list(generated_artifacts.get("artifact_bundle_registry_entries") or []):
            if not isinstance(entry, dict):
                continue
            artifact_bundle = entry.get("artifact_bundle") or {}
            bundle_members = list(entry.get("bundle_members") or [])
            _record(
                artifact_bundle_id=artifact_bundle.get("bundle_id"),
                artifact_kind=artifact_bundle.get("bundle_kind"),
                selected_member_ids=[
                    str(member.get("member_id"))
                    for member in bundle_members
                    if isinstance(member, dict) and str(member.get("member_id") or "").strip()
                ],
                source_capability=artifact_bundle.get("source_capability"),
                parse_capabilities_supported=[
                    str(cap)
                    for cap in artifact_bundle.get("parse_capabilities_supported") or []
                    if str(cap).strip()
                ],
            )
        return list(references_by_id.values())

    def _round_artifact_references(self, entry: WorkingMemoryEntry) -> list[PlannerArtifactReference]:
        references_by_id: dict[str, PlannerArtifactReference] = {}
        for agent_report in entry.agent_reports:
            compact = dict(agent_report.planner_compact_summary)
            for item in compact.get("artifact_references") or []:
                if not isinstance(item, dict):
                    continue
                bundle_id = str(item.get("artifact_bundle_id") or "").strip()
                if not bundle_id:
                    continue
                existing = references_by_id.get(bundle_id)
                if existing is None:
                    references_by_id[bundle_id] = PlannerArtifactReference.model_validate(item)
                    continue
                existing.selected_member_ids = list(
                    dict.fromkeys([*existing.selected_member_ids, *list(item.get("selected_member_ids") or [])])
                )
                existing.parse_capabilities_supported = list(
                    dict.fromkeys(
                        [*existing.parse_capabilities_supported, *list(item.get("parse_capabilities_supported") or [])]
                    )
                )
                if not existing.artifact_kind and item.get("artifact_kind"):
                    existing.artifact_kind = item.get("artifact_kind")
                if not existing.source_capability and item.get("source_capability"):
                    existing.source_capability = item.get("source_capability")
        return list(references_by_id.values())

    def _round_key_observations(self, entry: WorkingMemoryEntry) -> list[str]:
        observations: list[str] = []
        for agent_report in entry.agent_reports:
            compact = dict(agent_report.planner_compact_summary)
            for item in compact.get("key_observations") or []:
                text = str(item).strip()
                if text and text not in observations:
                    observations.append(text)
        if not observations and entry.evidence_summary:
            observations.append(self._truncate(entry.evidence_summary, 180))
        return observations[:5]

    def _round_missing_deliverables(self, entry: WorkingMemoryEntry) -> list[str]:
        missing: list[str] = []
        for agent_report in entry.agent_reports:
            compact = dict(agent_report.planner_compact_summary)
            for item in compact.get("key_missing_deliverables") or []:
                text = str(item).strip()
                if text and text not in missing:
                    missing.append(text)
        return missing

    def _round_status(self, entry: WorkingMemoryEntry) -> str:
        statuses = [agent_report.status for agent_report in entry.agent_reports]
        if not statuses:
            return "unknown"
        if any(status == "failed" for status in statuses):
            return "failed"
        if any(status == "partial" for status in statuses):
            return "partial"
        return "success"

    def _coverage_debt_delta(
        self,
        previous_entry: WorkingMemoryEntry | None,
        entry: WorkingMemoryEntry,
    ) -> str | None:
        previous = set(previous_entry.coverage_debt_hypotheses) if previous_entry is not None else set()
        current = set(entry.coverage_debt_hypotheses)
        cleared = sorted(previous - current)
        added = sorted(current - previous)
        parts: list[str] = []
        if cleared:
            parts.append(f"cleared: {', '.join(cleared)}")
        if added:
            parts.append(f"added: {', '.join(added)}")
        return "; ".join(parts) or None

    def _hypothesis_delta(
        self,
        previous_entry: WorkingMemoryEntry | None,
        entry: WorkingMemoryEntry,
    ) -> str | None:
        if previous_entry is None:
            return f"top1 initialized as {entry.current_hypothesis}"
        if previous_entry.current_hypothesis != entry.current_hypothesis:
            return f"top1 changed from {previous_entry.current_hypothesis} to {entry.current_hypothesis}"
        confidence_delta = round(entry.confidence - previous_entry.confidence, 3)
        if confidence_delta > 0:
            return f"top1 confidence increased by {confidence_delta:.3f}"
        if confidence_delta < 0:
            return f"top1 confidence decreased by {abs(confidence_delta):.3f}"
        return None

    def _compact_report_observation(self, report: Any) -> str:
        compact = self._planner_compact_summary(report)
        observations = [str(item).strip() for item in compact.get("key_observations") or [] if str(item).strip()]
        if observations:
            return self._truncate(" | ".join(observations), 220)
        return self._truncate(str(getattr(report, "planner_readable_report", "") or ""), 220)

    def _truncate(self, text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return f"{text[: limit - 3]}..."

    def _repeated_local_uncertainties(
        self,
        state: AieMasState,
        agent_reports: list[WorkingMemoryAgentEntry],
    ) -> list[str]:
        recent_texts = [
            report.remaining_local_uncertainty
            for entry in state.working_memory[-2:]
            for report in entry.agent_reports
            if report.remaining_local_uncertainty
        ]
        recent_texts.extend(
            report.remaining_local_uncertainty
            for report in agent_reports
            if report.remaining_local_uncertainty
        )
        return self._repeated_strings(recent_texts)

    def _repeated_strings(self, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values if value.strip()]
        counts = Counter(normalized)
        return [value for value, count in counts.items() if count >= 2]

    def _planned_action_label(self, state: AieMasState) -> str:
        decision = state.last_planner_decision
        if decision is None:
            return "unknown"
        if decision.action == "microscopic":
            candidate_texts = [
                str(decision.agent_task_instructions.get("microscopic") or "").strip(),
                str(decision.task_instruction or "").strip(),
            ]
            for text in candidate_texts:
                for capability_name in _MICROSCOPIC_ACTION_LABELS:
                    if capability_name in text:
                        return capability_name
        return decision.action

    def _executed_action_labels(self, reports: list[Any]) -> list[str]:
        labels: list[str] = []
        for report in reports:
            agent_name = getattr(report, "agent_name", None)
            if agent_name == "macro":
                labels.append("macro")
                continue
            if agent_name == "verifier":
                labels.append("verifier")
                continue
            if agent_name == "microscopic":
                structured_results = getattr(report, "structured_results", {}) or {}
                executed_capability = str(structured_results.get("executed_capability") or "").strip()
                labels.append(executed_capability or "microscopic")
        deduped: list[str] = []
        for label in labels:
            if label not in deduped:
                deduped.append(label)
        return deduped

    def _executed_evidence_families(self, action_labels: list[str]) -> list[EvidenceFamily]:
        families: list[EvidenceFamily] = []
        for label in action_labels:
            for family in _EVIDENCE_FAMILY_BY_ACTION.get(label, ()):
                if family not in families:
                    families.append(family)
        return families

    def _backfilled_task_instruction(
        self,
        *,
        planner_task_instruction: str | None,
        planner_agent_task_instructions: dict[str, str],
        planned_action_label: str | None,
        executed_action_labels: list[str],
    ) -> str | None:
        task_instruction = str(planner_task_instruction or "").strip()
        if task_instruction:
            return task_instruction
        if len(planner_agent_task_instructions) == 1:
            only_instruction = next(iter(planner_agent_task_instructions.values()), "").strip()
            if only_instruction:
                return only_instruction
        if planned_action_label:
            return planned_action_label
        if executed_action_labels:
            return ", ".join(executed_action_labels)
        return None
