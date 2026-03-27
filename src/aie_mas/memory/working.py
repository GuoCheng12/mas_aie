from __future__ import annotations

from collections import Counter

from aie_mas.graph.state import AieMasState, WorkingMemoryAgentEntry, WorkingMemoryEntry


class WorkingMemoryManager:
    def append_round_summary(self, state: AieMasState) -> AieMasState:
        if state.last_planner_decision is None:
            raise ValueError("Planner decision is required before updating working memory.")

        action_taken = ", ".join(report.agent_name for report in state.active_round_reports)
        if not action_taken:
            action_taken = state.last_planner_decision.action

        evidence_summary = " | ".join(
            f"{report.agent_name}: {report.planner_readable_report}" for report in state.active_round_reports
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
                generated_artifacts=dict(report.generated_artifacts),
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

        entry = WorkingMemoryEntry(
            round_id=state.round_idx + 1,
            current_hypothesis=state.current_hypothesis or "unknown",
            confidence=state.confidence or 0.0,
            hypothesis_pool=list(state.hypothesis_pool),
            runner_up_hypothesis=state.runner_up_hypothesis,
            runner_up_confidence=state.runner_up_confidence,
            action_taken=action_taken,
            evidence_summary=evidence_summary,
            diagnosis_summary=diagnosis_summary,
            main_gap=state.latest_main_gap or "Not specified.",
            conflict_status=state.latest_conflict_status or "unknown",
            next_action=state.last_planner_decision.action,
            planner_task_instruction=state.last_planner_decision.task_instruction,
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
            finalization_mode=state.last_planner_decision.finalization_mode,
            pairwise_verifier_completed_for_pair=state.last_planner_decision.pairwise_verifier_completed_for_pair,
            pairwise_verifier_evidence_specificity=state.last_planner_decision.pairwise_verifier_evidence_specificity,
            local_uncertainty_summary=local_uncertainty_summary,
            repeated_local_uncertainty_signals=repeated_local_uncertainty_signals,
            capability_lesson_candidates=list(state.last_planner_decision.capability_lesson_candidates),
            agent_reports=agent_reports,
        )
        state.working_memory.append(entry)
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
                    "finalization_mode": entry.finalization_mode,
                    "pairwise_verifier_completed_for_pair": entry.pairwise_verifier_completed_for_pair,
                    "pairwise_verifier_evidence_specificity": entry.pairwise_verifier_evidence_specificity,
                    "evidence_summary": self._truncate(entry.evidence_summary, 260),
                    "diagnosis_summary": self._truncate(entry.diagnosis_summary, 260),
                    "planner_task_instruction": self._truncate(entry.planner_task_instruction or "", 220),
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
                }
            )
        return context

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
            "low_information_round_ids": low_information_round_ids,
            "stagnation_round_ids": stagnation_round_ids,
        }

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
