from __future__ import annotations

from aie_mas.graph.state import AgentReport, MicroscopicTaskSpec
from aie_mas.tools.macro import MockMacroStructureTool
from aie_mas.tools.microscopic import (
    MockS0OptimizationTool,
    MockS1OptimizationTool,
    MockTargetedMicroscopicTool,
)
from aie_mas.tools.verifier import MockVerifierEvidenceTool


class MacroAgent:
    def __init__(self, tool: MockMacroStructureTool | None = None) -> None:
        self._tool = tool or MockMacroStructureTool()

    def run(self, smiles: str, task_received: str) -> AgentReport:
        raw_result = self._tool.invoke(smiles)
        return AgentReport(
            agent_name="macro",
            task_received=task_received,
            tool_calls=[f"{self._tool.name}(smiles='{smiles}')"],
            raw_results={"macro_structure_scan": raw_result},
            structured_results=raw_result,
            status="success",
            planner_readable_report=(
                f"Macro scan recorded aromatic_atom_count={raw_result['aromatic_atom_count']}, "
                f"hetero_atom_count={raw_result['hetero_atom_count']}, "
                f"branch_point_count={raw_result['branch_point_count']}, "
                f"conjugation_proxy={raw_result['conjugation_proxy']}, "
                f"flexibility_proxy={raw_result['flexibility_proxy']}."
            ),
        )


class MicroscopicAgent:
    def __init__(
        self,
        s0_tool: MockS0OptimizationTool | None = None,
        s1_tool: MockS1OptimizationTool | None = None,
        targeted_tool: MockTargetedMicroscopicTool | None = None,
    ) -> None:
        self._s0_tool = s0_tool or MockS0OptimizationTool()
        self._s1_tool = s1_tool or MockS1OptimizationTool()
        self._targeted_tool = targeted_tool or MockTargetedMicroscopicTool()

    def run(
        self,
        smiles: str,
        task_received: str,
        task_spec: MicroscopicTaskSpec | None = None,
    ) -> AgentReport:
        task_spec = task_spec or MicroscopicTaskSpec(
            mode="baseline_s0_s1",
            task_label="initial-baseline",
            objective="Run fixed first-stage S0/S1 optimization.",
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

        return AgentReport(
            agent_name="microscopic",
            task_received=task_received,
            tool_calls=tool_calls,
            raw_results=raw_results,
            structured_results=structured_results,
            status="success",
            planner_readable_report=(
                f"Microscopic run ({task_spec.mode}) recorded s0_energy={structured_results['s0_energy']}, "
                f"s1_energy={structured_results['s1_energy']}, "
                f"geometry_change_proxy={structured_results['geometry_change_proxy']}, "
                f"oscillator_strength_proxy={structured_results['oscillator_strength_proxy']}, "
                f"relaxation_gap={structured_results['relaxation_gap']}."
            ),
        )


class VerifierAgent:
    def __init__(self, tool: MockVerifierEvidenceTool | None = None) -> None:
        self._tool = tool or MockVerifierEvidenceTool()

    def run(self, smiles: str, current_hypothesis: str, task_received: str) -> AgentReport:
        raw_result = self._tool.invoke(smiles, current_hypothesis)
        return AgentReport(
            agent_name="verifier",
            task_received=task_received,
            tool_calls=[
                f"{self._tool.name}(smiles='{smiles}', current_hypothesis='{current_hypothesis}')"
            ],
            raw_results={"verifier_lookup": raw_result},
            structured_results=raw_result,
            status="success",
            planner_readable_report=(
                f"Verifier gathered {raw_result['source_count']} evidence card(s) for hypothesis "
                f"'{current_hypothesis}'."
            ),
        )
