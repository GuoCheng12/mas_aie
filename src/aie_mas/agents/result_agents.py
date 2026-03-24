from __future__ import annotations

from pathlib import Path

from aie_mas.agents.macro import MacroAgent
from aie_mas.agents.microscopic import MicroscopicAgent
from aie_mas.graph.state import AgentReport
from aie_mas.tools.verifier import MockVerifierEvidenceTool
from aie_mas.utils.prompts import PromptRepository


def _default_prompt_repository() -> PromptRepository:
    return PromptRepository(Path(__file__).resolve().parents[1] / "prompts")


class VerifierAgent:
    def __init__(
        self,
        tool: MockVerifierEvidenceTool | None = None,
        prompts: PromptRepository | None = None,
    ) -> None:
        self._tool = tool or MockVerifierEvidenceTool()
        self._prompts = prompts or _default_prompt_repository()

    def run(self, smiles: str, current_hypothesis: str, task_received: str) -> AgentReport:
        draft = self._prompts.render_sections(
            "verifier_specialized",
            {
                "task_received": task_received,
                "current_hypothesis": current_hypothesis,
                "tool_name": self._tool.name,
                "task_completion_text": "Task completion is pending verifier evidence retrieval.",
                "source_count": "pending",
                "topic_summary": "pending",
                "local_uncertainty_detail": (
                    "the evidence cards still need Planner-level synthesis before any mechanism decision."
                ),
            },
        )
        raw_result = self._tool.invoke(smiles, current_hypothesis)
        cards = raw_result["evidence_cards"]
        topic_summary = _topic_summary(cards)
        task_completion_status, task_completion_text = self._task_completion(raw_result["source_count"])
        rendered = self._prompts.render_sections(
            "verifier_specialized",
            {
                "task_received": task_received,
                "current_hypothesis": current_hypothesis,
                "tool_name": self._tool.name,
                "task_completion_text": task_completion_text,
                "source_count": raw_result["source_count"],
                "topic_summary": topic_summary,
                "local_uncertainty_detail": (
                    "the evidence cards still need Planner-level synthesis before any mechanism decision."
                ),
            },
        )
        structured_results = dict(raw_result)
        structured_results["topic_summary"] = topic_summary
        structured_results["task_completion_status"] = task_completion_status
        structured_results["task_completion"] = rendered["task_completion"]
        return AgentReport(
            agent_name="verifier",
            task_received=task_received,
            task_completion_status=task_completion_status,
            task_completion=rendered["task_completion"],
            task_understanding=draft["task_understanding"],
            execution_plan=draft["execution_plan"],
            result_summary=rendered["result_summary"],
            remaining_local_uncertainty=rendered["remaining_local_uncertainty"],
            tool_calls=[
                f"{self._tool.name}(smiles='{smiles}', current_hypothesis='{current_hypothesis}')"
            ],
            raw_results={"verifier_lookup": raw_result},
            structured_results=structured_results,
            generated_artifacts={},
            status="success",
            planner_readable_report=rendered["planner_readable_report"],
        )

    def _task_completion(self, source_count: int) -> tuple[str, str]:
        if source_count <= 0:
            return (
                "partial",
                "Task only partially completed. The verifier executed the retrieval step, but no relevant evidence cards were found.",
            )
        return (
            "completed",
            "Task completed successfully by retrieving raw verifier evidence for Planner review.",
        )


def _topic_summary(cards: list[dict[str, object]]) -> str:
    topics: list[str] = []
    for card in cards:
        for tag in card.get("topic_tags", []):
            tag_text = str(tag).strip()
            if tag_text and tag_text not in topics:
                topics.append(tag_text)
    return ", ".join(topics) if topics else "no specific topic tags"
