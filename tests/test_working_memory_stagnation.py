from __future__ import annotations

from aie_mas.graph.state import AieMasState, WorkingMemoryEntry
from aie_mas.memory.working import WorkingMemoryManager


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
    assert "reasoning_phase" in context[0]
    assert "executed_evidence_families" in context[2]
