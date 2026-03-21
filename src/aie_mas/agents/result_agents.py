from __future__ import annotations

from pathlib import Path
from typing import Any

from aie_mas.graph.state import AgentReport, MicroscopicTaskSpec
from aie_mas.tools.macro import MockMacroStructureTool
from aie_mas.tools.microscopic import (
    MockS0OptimizationTool,
    MockS1OptimizationTool,
    MockTargetedMicroscopicTool,
)
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
            status="success",
            planner_readable_report=rendered["planner_readable_report"],
        )


class MicroscopicAgent:
    def __init__(
        self,
        s0_tool: MockS0OptimizationTool | None = None,
        s1_tool: MockS1OptimizationTool | None = None,
        targeted_tool: MockTargetedMicroscopicTool | None = None,
        prompts: PromptRepository | None = None,
    ) -> None:
        self._s0_tool = s0_tool or MockS0OptimizationTool()
        self._s1_tool = s1_tool or MockS1OptimizationTool()
        self._targeted_tool = targeted_tool or MockTargetedMicroscopicTool()
        self._prompts = prompts or _default_prompt_repository()

    def run(
        self,
        smiles: str,
        task_received: str,
        task_spec: MicroscopicTaskSpec | None = None,
        current_hypothesis: str = "unknown",
    ) -> AgentReport:
        task_spec = task_spec or MicroscopicTaskSpec(
            mode="baseline_s0_s1",
            task_label="initial-baseline",
            objective="Run fixed first-stage S0/S1 optimization.",
        )
        draft = self._prompts.render_sections(
            "microscopic_specialized",
            {
                "task_received": task_received,
                "current_hypothesis": current_hypothesis,
                "task_mode": task_spec.mode,
                "baseline_tools": f"{self._s0_tool.name} and {self._s1_tool.name}",
                "targeted_plan": self._targeted_plan_text(task_spec),
                "targeted_summary": self._targeted_summary_text(None),
                "local_uncertainty_detail": self._micro_uncertainty_text(task_spec),
                "s0_energy": "pending",
                "s1_energy": "pending",
                "rigidity_proxy": "pending",
                "geometry_change_proxy": "pending",
                "oscillator_strength_proxy": "pending",
                "relaxation_gap": "pending",
            },
        )

        s0_result = self._s0_tool.invoke(smiles)
        s1_result = self._s1_tool.invoke(smiles)
        relaxation_gap = round(abs(s1_result["optimized_energy"] - s0_result["optimized_energy"]), 4)
        structured_results = {
            "task_mode": task_spec.mode,
            "task_label": task_spec.task_label,
            "task_objective": task_spec.objective,
            "target_property": task_spec.target_property,
            "s0_energy": s0_result["optimized_energy"],
            "s1_energy": s1_result["optimized_energy"],
            "rigidity_proxy": s0_result["rigidity_proxy"],
            "geometry_change_proxy": s1_result["geometry_change_proxy"],
            "oscillator_strength_proxy": s1_result["oscillator_strength_proxy"],
            "relaxation_gap": relaxation_gap,
        }
        tool_calls = [
            f"{self._s0_tool.name}(smiles='{smiles}')",
            f"{self._s1_tool.name}(smiles='{smiles}')",
        ]
        raw_results = {"s0_optimization": s0_result, "s1_optimization": s1_result}

        targeted_result: dict[str, Any] | None = None
        if task_spec.mode == "targeted_follow_up":
            targeted_result = self._targeted_tool.invoke(
                smiles,
                objective=task_spec.objective,
                target_property=task_spec.target_property,
            )
            structured_results["targeted_follow_up"] = targeted_result
            raw_results["targeted_follow_up"] = targeted_result
            tool_calls.append(
                f"{self._targeted_tool.name}(smiles='{smiles}', objective='{task_spec.objective}')"
            )

        rendered = self._prompts.render_sections(
            "microscopic_specialized",
            {
                "task_received": task_received,
                "current_hypothesis": current_hypothesis,
                "task_mode": task_spec.mode,
                "baseline_tools": f"{self._s0_tool.name} and {self._s1_tool.name}",
                "targeted_plan": self._targeted_plan_text(task_spec),
                "targeted_summary": self._targeted_summary_text(targeted_result),
                "local_uncertainty_detail": self._micro_uncertainty_text(task_spec),
                "s0_energy": structured_results["s0_energy"],
                "s1_energy": structured_results["s1_energy"],
                "rigidity_proxy": structured_results["rigidity_proxy"],
                "geometry_change_proxy": structured_results["geometry_change_proxy"],
                "oscillator_strength_proxy": structured_results["oscillator_strength_proxy"],
                "relaxation_gap": structured_results["relaxation_gap"],
            },
        )

        return AgentReport(
            agent_name="microscopic",
            task_received=task_received,
            task_understanding=draft["task_understanding"],
            execution_plan=draft["execution_plan"],
            result_summary=rendered["result_summary"],
            remaining_local_uncertainty=rendered["remaining_local_uncertainty"],
            tool_calls=tool_calls,
            raw_results=raw_results,
            structured_results=structured_results,
            status="success",
            planner_readable_report=rendered["planner_readable_report"],
        )

    def _targeted_plan_text(self, task_spec: MicroscopicTaskSpec) -> str:
        if task_spec.mode != "targeted_follow_up":
            return "No targeted follow-up tool is used in this baseline run."
        return (
            f"Use {self._targeted_tool.name} to probe the requested local target "
            f"'{task_spec.target_property or 'follow_up_consistency'}' for this follow-up task."
        )

    def _targeted_summary_text(self, targeted_result: dict[str, Any] | None) -> str:
        if targeted_result is None:
            return "No targeted follow-up result was produced in this run."
        return (
            "Targeted follow-up recorded "
            f"consistency_proxy={targeted_result['consistency_proxy']} and "
            f"constraint_sensitivity={targeted_result['constraint_sensitivity']}."
        )

    def _micro_uncertainty_text(self, task_spec: MicroscopicTaskSpec) -> str:
        if task_spec.mode == "targeted_follow_up":
            return (
                "the targeted micro follow-up still cannot establish verifier-aligned mechanism selection "
                "without Planner-level synthesis."
            )
        return "the baseline S0/S1 proxy run still cannot determine external consistency or final mechanism."


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
            status="success",
            planner_readable_report=rendered["planner_readable_report"],
        )
