from __future__ import annotations

from pathlib import Path

from aie_mas.agents.planner import PlannerAgent
from aie_mas.config import AieMasConfig
from aie_mas.graph.state import AieMasState, AgentReport, WorkingMemoryEntry
from aie_mas.memory.working import WorkingMemoryManager
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


def test_recent_rounds_context_keeps_latest_action_gap_and_summaries() -> None:
    manager = WorkingMemoryManager()
    state = AieMasState(
        user_query="Assess the likely AIE mechanism for this molecule.",
        smiles="C1=CC=CC=C1",
        working_memory=[
            WorkingMemoryEntry(
                round_id=1,
                current_hypothesis="RIM",
                confidence=0.41,
                action_taken="macro, microscopic",
                evidence_summary="round 1 evidence",
                diagnosis_summary="round 1 diagnosis",
                main_gap="Verifier evidence is required.",
                conflict_status="none",
                next_action="microscopic",
            ),
            WorkingMemoryEntry(
                round_id=2,
                current_hypothesis="RIM",
                confidence=0.45,
                action_taken="microscopic",
                evidence_summary="round 2 evidence",
                diagnosis_summary="round 2 diagnosis",
                main_gap="Micro consistency is still weak.",
                conflict_status="none",
                next_action="microscopic",
            ),
            WorkingMemoryEntry(
                round_id=3,
                current_hypothesis="RIM",
                confidence=0.49,
                action_taken="microscopic",
                evidence_summary="round 3 evidence",
                diagnosis_summary="round 3 diagnosis",
                main_gap="Micro consistency is still weak.",
                conflict_status="none",
                next_action="verifier",
            ),
            WorkingMemoryEntry(
                round_id=4,
                current_hypothesis="RIM",
                confidence=0.5,
                action_taken="verifier",
                evidence_summary="round 4 evidence",
                diagnosis_summary="round 4 diagnosis",
                main_gap="External supervision is pending.",
                conflict_status="none",
                next_action="finalize",
            ),
        ],
    )

    context = manager.build_recent_rounds_context(state)

    assert len(context) == 3
    assert [entry["round_id"] for entry in context] == [2, 3, 4]
    assert context[0]["action_taken"] == "microscopic"
    assert context[1]["main_gap"] == "Micro consistency is still weak."
    assert context[2]["evidence_summary"] == "round 4 evidence"
    assert context[2]["diagnosis_summary"] == "round 4 diagnosis"
    assert "capability_assessment" in context[0]
    assert "local_uncertainty_summary" in context[1]
    assert "repeated_local_uncertainty_signals" in context[2]


def test_planner_marks_stagnation_and_finalizes_with_bounded_uncertainty(tmp_path: Path) -> None:
    planner = _build_planner(tmp_path)
    state = AieMasState(
        user_query="Assess the likely AIE mechanism for this molecule.",
        smiles="C(c1ccccc1)(c1ccccc1)=C(c1ccccc1)c1ccccc1",
        current_hypothesis="restriction of intramolecular motion (RIM)-dominated AIE",
        confidence=0.43,
        working_memory=[
            WorkingMemoryEntry(
                round_id=1,
                current_hypothesis="restriction of intramolecular motion (RIM)-dominated AIE",
                confidence=0.41,
                action_taken="microscopic",
                evidence_summary="Only incremental micro proxy changes were observed.",
                diagnosis_summary="The main gap remains verifier evidence.",
                main_gap="Verifier evidence is required before a temporary conclusion can be trusted.",
                conflict_status="none",
                next_action="microscopic",
            ),
            WorkingMemoryEntry(
                round_id=2,
                current_hypothesis="restriction of intramolecular motion (RIM)-dominated AIE",
                confidence=0.42,
                action_taken="microscopic",
                evidence_summary="The same micro proxy pattern was seen again.",
                diagnosis_summary="The main gap remains verifier evidence.",
                main_gap="Verifier evidence is required before a temporary conclusion can be trusted.",
                conflict_status="none",
                next_action="microscopic",
            ),
        ],
        macro_reports=[
            AgentReport(
                agent_name="macro",
                task_received="Return low-cost structure results.",
                remaining_local_uncertainty="Macro structure proxies are repeating and cannot separate RIM from packing effects.",
                tool_calls=["mock_macro_tool"],
                raw_results={"macro_tool": {"aromatic_atom_count": 4}},
                structured_results={
                    "aromatic_atom_count": 4,
                    "branch_point_count": 0,
                    "flexibility_proxy": 1.2,
                },
                status="success",
                planner_readable_report="Macro report with limited incremental evidence.",
            )
        ],
        microscopic_reports=[
            AgentReport(
                agent_name="microscopic",
                task_received="Return micro proxy results.",
                remaining_local_uncertainty="Microscopic proxy evidence remains too weak to break the current gap.",
                tool_calls=["mock_s0_tool", "mock_s1_tool"],
                raw_results={"micro_tool": {"relaxation_gap": 0.12}},
                structured_results={
                    "relaxation_gap": 0.12,
                    "geometry_change_proxy": 0.88,
                    "oscillator_strength_proxy": 0.14,
                },
                status="success",
                planner_readable_report="Microscopic report with limited incremental evidence.",
            )
        ],
    )

    result = planner.plan_diagnosis(state)
    decision = result["decision"]

    assert decision.action == "finalize"
    assert decision.needs_verifier is False
    assert decision.finalize is True
    assert decision.stagnation_detected is True
    assert decision.hypothesis_uncertainty_note
    assert decision.capability_assessment
    assert decision.stagnation_assessment
    assert decision.contraction_reason
    assert decision.capability_lesson_candidates
    assert "limited new information" in result["information_gain_assessment"]
    assert "not shrinking" in result["gap_trend"]
    assert "capability-limited" in result["main_gap"].lower()
