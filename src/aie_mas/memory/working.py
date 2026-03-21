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
                    "action_taken": entry.action_taken,
                    "main_gap": entry.main_gap,
                    "evidence_summary": self._truncate(entry.evidence_summary, 260),
                    "diagnosis_summary": self._truncate(entry.diagnosis_summary, 260),
                }
            )
        return context

    def _truncate(self, text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return f"{text[: limit - 3]}..."
