from __future__ import annotations

from pathlib import Path

from aie_mas.agents.planner import PlannerAgent
from aie_mas.config import AieMasConfig
from aie_mas.graph.state import AieMasState
from aie_mas.utils.prompts import PromptRepository


PROMPTS_DIR = Path(__file__).resolve().parents[1] / "src" / "aie_mas" / "prompts"


def _build_planner(tmp_path: Path) -> PlannerAgent:
    config = AieMasConfig(
        project_root=tmp_path,
        execution_profile="local-dev",
        planner_backend="mock",
        prompts_dir=PROMPTS_DIR,
    )
    return PlannerAgent(PromptRepository(PROMPTS_DIR), config=config)


def test_initial_planner_dispatch_contains_agent_task_instructions(tmp_path: Path) -> None:
    planner = _build_planner(tmp_path)
    result = planner.plan_initial(
        AieMasState(
            user_query="Assess the likely AIE mechanism for this molecule.",
            smiles="C(c1ccccc1)(c1ccccc1)=C(c1ccccc1)c1ccccc1",
        )
    )

    decision = result["decision"]
    top_hypothesis = result["hypothesis_pool"][0]

    assert decision.action == "macro_and_microscopic"
    assert decision.task_instruction
    assert "macro" in decision.agent_task_instructions
    assert "microscopic" in decision.agent_task_instructions
    assert "current working hypothesis" in decision.agent_task_instructions["macro"]
    assert "S0/S1" in decision.agent_task_instructions["microscopic"]
    assert top_hypothesis.candidate_strength == "medium"
    assert "generic mock fallback" in decision.hypothesis_uncertainty_note.lower()
    assert "specialized agents" in decision.capability_assessment.lower()
