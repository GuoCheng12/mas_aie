from __future__ import annotations

import inspect
from pathlib import Path

from aie_mas.config import AieMasConfig
from aie_mas.agents.macro import MacroAgent
from aie_mas.agents.microscopic import MicroscopicAgent
from aie_mas.graph.state import AgentReport, MoleculeIdentityContext
from aie_mas.tools.verifier import OpenAIVerifierEvidenceTool
from aie_mas.utils.prompts import PromptRepository


def _default_prompt_repository() -> PromptRepository:
    return PromptRepository(Path(__file__).resolve().parents[1] / "prompts")


class VerifierAgent:
    def __init__(
        self,
        tool: OpenAIVerifierEvidenceTool | None = None,
        prompts: PromptRepository | None = None,
        config: AieMasConfig | None = None,
    ) -> None:
        self._config = config or AieMasConfig()
        self._tool = tool or OpenAIVerifierEvidenceTool(config=self._config)
        self._prompts = prompts or _default_prompt_repository()

    def run(
        self,
        smiles: str,
        current_hypothesis: str,
        task_received: str,
        *,
        champion_hypothesis: str | None = None,
        challenger_hypothesis: str | None = None,
        pairwise_decision_question: str | None = None,
        main_gap: str,
        molecule_identity_context: MoleculeIdentityContext | None = None,
        latest_macro_report: AgentReport | None = None,
        latest_microscopic_report: AgentReport | None = None,
    ) -> AgentReport:
        champion_hypothesis = champion_hypothesis or current_hypothesis
        challenger_hypothesis = challenger_hypothesis or "unknown"
        pairwise_decision_question = pairwise_decision_question or (
            f"Distinguish '{champion_hypothesis}' versus '{challenger_hypothesis}' for the current molecule. "
            f"The unresolved discriminator is: {main_gap}"
        )
        draft = self._prompts.render_sections(
            "verifier_specialized",
            {
                "task_received": task_received,
                "current_hypothesis": current_hypothesis,
                "tool_name": self._tool.name,
                "task_completion_text": "Task completion is pending verifier evidence retrieval.",
                "source_count": "pending",
                "topic_summary": "pending",
                "query_groups_attempted": "pending",
                "local_uncertainty_detail": (
                    "the evidence cards still need Planner-level synthesis before any mechanism decision."
                ),
            },
        )
        invoke_kwargs = {
            "smiles": smiles,
            "current_hypothesis": current_hypothesis,
            "champion_hypothesis": champion_hypothesis,
            "challenger_hypothesis": challenger_hypothesis,
            "pairwise_decision_question": pairwise_decision_question,
            "task_received": task_received,
            "main_gap": main_gap,
            "molecule_identity_context": molecule_identity_context,
            "latest_macro_report": latest_macro_report,
            "latest_microscopic_report": latest_microscopic_report,
        }
        accepted_parameters = set(inspect.signature(self._tool.invoke).parameters)
        raw_result = self._tool.invoke(
            **{key: value for key, value in invoke_kwargs.items() if key in accepted_parameters}
        )
        cards = raw_result["evidence_cards"]
        topic_summary = _topic_summary(cards)
        task_completion_status, task_completion_text = self._task_completion(raw_result)
        rendered = self._prompts.render_sections(
            "verifier_specialized",
            {
                "task_received": task_received,
                "current_hypothesis": current_hypothesis,
                "tool_name": self._tool.name,
                "task_completion_text": task_completion_text,
                "source_count": raw_result["source_count"],
                "topic_summary": topic_summary,
                "query_groups_attempted": ", ".join(raw_result.get("query_groups_attempted", [])) or "none",
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
                (
                    f"{self._tool.name}(smiles='{smiles}', current_hypothesis='{current_hypothesis}', "
                    f"champion_hypothesis='{champion_hypothesis}', "
                    f"challenger_hypothesis='{challenger_hypothesis}', main_gap='{main_gap}')"
                )
            ],
            raw_results={"verifier_lookup": raw_result},
            structured_results=structured_results,
            generated_artifacts={},
            status=self._report_status(raw_result),
            planner_readable_report=rendered["planner_readable_report"],
        )

    def _task_completion(self, raw_result: dict[str, object]) -> tuple[str, str]:
        status = str(raw_result.get("status") or "success")
        source_count = int(raw_result.get("source_count") or 0)
        if status == "failed":
            return (
                "failed",
                "Task failed because verifier retrieval did not return usable external evidence cards.",
            )
        if status == "partial" or source_count <= 0:
            return (
                "partial",
                "Task only partially completed. The verifier retrieved limited external material and returned only partial external evidence.",
            )
        return (
            "completed",
            "Task completed successfully by retrieving raw verifier evidence for Planner review.",
        )

    def _report_status(self, raw_result: dict[str, object]) -> str:
        status = str(raw_result.get("status") or "success")
        if status == "failed":
            return "failed"
        if status == "partial":
            return "partial"
        return "success"


def _topic_summary(cards: list[dict[str, object]]) -> str:
    topics: list[str] = []
    for card in cards:
        for tag in card.get("topic_tags", []):
            tag_text = str(tag).strip()
            if tag_text and tag_text not in topics:
                topics.append(tag_text)
    return ", ".join(topics) if topics else "no specific topic tags"
