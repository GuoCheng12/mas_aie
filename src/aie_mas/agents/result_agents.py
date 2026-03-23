from __future__ import annotations

from pathlib import Path

from aie_mas.agents.microscopic import MicroscopicAgent
from aie_mas.graph.state import AgentReport
from aie_mas.tools.macro import MockMacroStructureTool
from aie_mas.tools.verifier import MockVerifierEvidenceTool
from aie_mas.utils.prompts import PromptRepository


def _default_prompt_repository() -> PromptRepository:
    return PromptRepository(Path(__file__).resolve().parents[1] / "prompts")


class MacroAgent:
    def __init__(
        self,
        tool: MockMacroStructureTool | None = None,
        prompts: PromptRepository | None = None,
    ) -> None:
        self._tool = tool or MockMacroStructureTool()
        self._prompts = prompts or _default_prompt_repository()

    def run(
        self,
        smiles: str,
        task_received: str,
        current_hypothesis: str = "unknown",
    ) -> AgentReport:
        draft = self._prompts.render_sections(
            "macro_specialized",
            {
                "task_received": task_received,
                "current_hypothesis": current_hypothesis,
                "tool_name": self._tool.name,
                "aromatic_atom_count": "pending",
                "hetero_atom_count": "pending",
                "branch_point_count": "pending",
                "conjugation_proxy": "pending",
                "flexibility_proxy": "pending",
                "local_uncertainty_detail": (
                    "the macro scan cannot determine excited-state relaxation behavior or external support."
                ),
            },
        )
        raw_result = self._tool.invoke(smiles)
        rendered = self._prompts.render_sections(
            "macro_specialized",
            {
                "task_received": task_received,
                "current_hypothesis": current_hypothesis,
                "tool_name": self._tool.name,
                "aromatic_atom_count": raw_result["aromatic_atom_count"],
                "hetero_atom_count": raw_result["hetero_atom_count"],
                "branch_point_count": raw_result["branch_point_count"],
                "conjugation_proxy": raw_result["conjugation_proxy"],
                "flexibility_proxy": raw_result["flexibility_proxy"],
                "local_uncertainty_detail": (
                    "the macro scan cannot determine excited-state relaxation behavior or external support."
                ),
            },
        )
        return AgentReport(
            agent_name="macro",
            task_received=task_received,
            task_understanding=draft["task_understanding"],
            execution_plan=draft["execution_plan"],
            result_summary=rendered["result_summary"],
            remaining_local_uncertainty=rendered["remaining_local_uncertainty"],
            tool_calls=[f"{self._tool.name}(smiles='{smiles}')"],
            raw_results={"macro_structure_scan": raw_result},
            structured_results=raw_result,
            generated_artifacts={},
            status="success",
            planner_readable_report=rendered["planner_readable_report"],
        )


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
                "source_count": "pending",
                "support_count": "pending",
                "conflict_count": "pending",
                "neutral_count": "pending",
                "local_uncertainty_detail": (
                    "the evidence cards still need Planner-level synthesis before any mechanism decision."
                ),
            },
        )
        raw_result = self._tool.invoke(smiles, current_hypothesis)
        cards = raw_result["evidence_cards"]
        support_count = sum(card["relation_to_hypothesis"] == "support" for card in cards)
        conflict_count = sum(card["relation_to_hypothesis"] == "conflict" for card in cards)
        neutral_count = sum(card["relation_to_hypothesis"] == "neutral" for card in cards)
        rendered = self._prompts.render_sections(
            "verifier_specialized",
            {
                "task_received": task_received,
                "current_hypothesis": current_hypothesis,
                "tool_name": self._tool.name,
                "source_count": raw_result["source_count"],
                "support_count": support_count,
                "conflict_count": conflict_count,
                "neutral_count": neutral_count,
                "local_uncertainty_detail": (
                    "the evidence cards still need Planner-level synthesis before any mechanism decision."
                ),
            },
        )
        structured_results = dict(raw_result)
        structured_results.update(
            {
                "support_count": support_count,
                "conflict_count": conflict_count,
                "neutral_count": neutral_count,
            }
        )
        return AgentReport(
            agent_name="verifier",
            task_received=task_received,
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
