from __future__ import annotations

from aie_mas.graph.state import AieMasState, WorkingMemoryEntry


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

        entry = WorkingMemoryEntry(
            round_id=state.round_idx + 1,
            current_hypothesis=state.current_hypothesis or "unknown",
            confidence=state.confidence or 0.0,
            action_taken=action_taken,
            evidence_summary=evidence_summary,
            diagnosis_summary=diagnosis_summary,
            main_gap=state.latest_main_gap or "Not specified.",
            conflict_status=state.latest_conflict_status or "unknown",
            next_action=state.last_planner_decision.action,
        )
        state.working_memory.append(entry)
        state.round_idx += 1
        state.active_round_reports.clear()
        return state
