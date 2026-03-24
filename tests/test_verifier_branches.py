from __future__ import annotations

from pathlib import Path

from aie_mas.agents.planner import PlannerAgent
from aie_mas.config import AieMasConfig
from aie_mas.graph.state import AieMasState, AgentReport, HypothesisEntry
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


def _build_state(cards: list[dict[str, str]]) -> AieMasState:
    return AieMasState(
        user_query="Assess the likely AIE mechanism for this molecule.",
        smiles="C(c1ccccc1)(c1ccccc1)=C(c1ccccc1)c1ccccc1",
        current_hypothesis="restriction of intramolecular motion (RIM)-dominated AIE",
        confidence=0.86,
        hypothesis_pool=[
            HypothesisEntry(name="restriction of intramolecular motion (RIM)-dominated AIE", confidence=0.44),
            HypothesisEntry(name="ICT-assisted emission with aggregation-enabled rigidification", confidence=0.28),
        ],
        verifier_reports=[
            AgentReport(
                agent_name="verifier",
                task_received="Return evidence cards.",
                tool_calls=["mock_verifier_tool"],
                raw_results={"verifier_lookup": {"evidence_cards": cards}},
                structured_results={"evidence_cards": cards, "source_count": len(cards)},
                status="success",
                planner_readable_report="Verifier report for branch test.",
            )
        ],
    )


def test_verifier_support_branch_finalizes(tmp_path: Path) -> None:
    planner = _build_planner(tmp_path)
    state = _build_state(
        [
            {
                "card_id": "s1",
                "source": "s1",
                "observation": "Restriction-oriented external note 1",
                "topic_tags": ["restriction", "branching"],
                "evidence_kind": "case_memory",
            },
            {
                "card_id": "s2",
                "source": "s2",
                "observation": "Restriction-oriented external note 2",
                "topic_tags": ["restriction"],
                "evidence_kind": "external_summary",
            },
        ]
    )

    result = planner.plan_reweight_or_finalize(state)

    assert result["decision"].action == "finalize"
    assert result["decision"].finalize is True
    assert result["decision"].task_instruction is None
    assert result["conflict_status"] == "none"
    assert result["decision"].contraction_reason
    assert "supports the current hypothesis" in result["decision"].diagnosis.lower()


def test_verifier_weak_conflict_branch_continues_refine(tmp_path: Path) -> None:
    planner = _build_planner(tmp_path)
    state = _build_state(
        [
            {
                "card_id": "s1",
                "source": "s1",
                "observation": "Restriction-oriented external note 1",
                "topic_tags": ["restriction", "branching"],
                "evidence_kind": "case_memory",
            },
            {
                "card_id": "c1",
                "source": "c1",
                "observation": "ICT-oriented external note 1",
                "topic_tags": ["ict", "heteroatom"],
                "evidence_kind": "external_summary",
            },
        ]
    )

    result = planner.plan_reweight_or_finalize(state)

    assert result["decision"].action == "microscopic"
    assert result["decision"].finalize is False
    assert result["decision"].current_hypothesis == state.current_hypothesis
    assert result["decision"].task_instruction
    assert result["conflict_status"] == "weak"
    assert result["decision"].capability_assessment
    assert result["decision"].contraction_reason
    assert "weak conflict" in result["decision"].diagnosis.lower()


def test_verifier_strong_conflict_branch_switches_hypothesis(tmp_path: Path) -> None:
    planner = _build_planner(tmp_path)
    state = _build_state(
        [
            {
                "card_id": "c1",
                "source": "c1",
                "observation": "ICT-oriented external note 1",
                "topic_tags": ["ict", "heteroatom"],
                "evidence_kind": "external_summary",
            },
            {
                "card_id": "c2",
                "source": "c2",
                "observation": "Second ICT-oriented external note",
                "topic_tags": ["ict"],
                "evidence_kind": "mechanistic_note",
            },
        ]
    )

    result = planner.plan_reweight_or_finalize(state)

    assert result["decision"].action == "macro"
    assert result["decision"].finalize is False
    assert result["decision"].current_hypothesis == "ICT-assisted emission with aggregation-enabled rigidification"
    assert result["decision"].task_instruction
    assert result["conflict_status"] == "strong"
    assert result["decision"].contraction_reason
    assert "strong conflict" in result["decision"].diagnosis.lower()
