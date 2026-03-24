from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aie_mas.agents.planner import PlannerAgent
from aie_mas.cli.run_case import run_case_workflow
from aie_mas.config import AieMasConfig
from aie_mas.graph.state import AieMasState
from aie_mas.utils.prompts import PromptRepository


PROMPTS_DIR = Path(__file__).resolve().parents[1] / "src" / "aie_mas" / "prompts"


@dataclass(frozen=True)
class MockCase:
    name: str
    smiles: str


MOCK_CASES = [
    MockCase(
        name="bulky_rim_case",
        smiles="C(c1ccccc1)(c1ccccc1)=C(c1ccccc1)c1ccccc1",
    ),
    MockCase(
        name="non_esipt_hydrocarbon_case",
        smiles="c1ccccc1",
    ),
    MockCase(
        name="ict_donor_acceptor_case",
        smiles="O=N(=O)c1ccc(N(CC)CC)cc1",
    ),
]


def _build_planner(tmp_path: Path) -> PlannerAgent:
    config = AieMasConfig(
        project_root=tmp_path,
        execution_profile="local-dev",
        planner_backend="mock",
        prompts_dir=PROMPTS_DIR,
    )
    return PlannerAgent(PromptRepository(PROMPTS_DIR), config=config)


def _run_case(case: MockCase, tmp_path: Path) -> AieMasState:
    case_dir = tmp_path / case.name
    return run_case_workflow(
        smiles=case.smiles,
        user_query="Assess the likely AIE mechanism for this molecule.",
        execution_profile="local-dev",
        planner_backend="mock",
        tool_backend="mock",
        enable_long_term_memory=False,
        prompts_dir=PROMPTS_DIR,
        data_dir=case_dir / "data",
        memory_dir=case_dir / "memory",
        report_dir=case_dir / "reports",
        log_dir=case_dir / "log",
        runtime_dir=case_dir / "runtime",
    )


def test_mock_cases_generate_generic_fallback_dispatch_with_nonempty_task_instructions(tmp_path: Path) -> None:
    planner = _build_planner(tmp_path)
    initial_results = {
        case.name: planner.plan_initial(
            AieMasState(
                user_query="Assess the likely AIE mechanism for this molecule.",
                smiles=case.smiles,
            )
        )
        for case in MOCK_CASES
    }

    for case in MOCK_CASES:
        result = initial_results[case.name]
        decision = result["decision"]
        assert decision.task_instruction
        assert decision.agent_task_instructions
        assert "macro" in decision.agent_task_instructions
        assert "microscopic" in decision.agent_task_instructions
        assert decision.agent_task_instructions["macro"]
        assert decision.agent_task_instructions["microscopic"]
        assert decision.hypothesis_uncertainty_note
        assert decision.capability_assessment
        assert "generic mock fallback" in decision.hypothesis_uncertainty_note.lower()
        assert result["hypothesis_pool"][0].candidate_strength == "medium"


def test_mock_cases_preserve_specialized_reports_and_diverge_in_workflow_behavior(
    tmp_path: Path,
    install_specialized_test_doubles,
) -> None:
    install_specialized_test_doubles()
    states = {case.name: _run_case(case, tmp_path) for case in MOCK_CASES}

    for case in MOCK_CASES:
        state = states[case.name]
        assert state.state_snapshot is not None
        assert state.macro_reports
        assert state.microscopic_reports
        assert state.working_memory

        first_macro = state.macro_reports[0]
        first_micro = state.microscopic_reports[0]
        for report in (first_macro, first_micro):
            assert report.task_understanding
            assert report.execution_plan
            assert report.result_summary
            assert report.remaining_local_uncertainty
            assert "Task understanding:" in report.planner_readable_report
            assert "Execution plan:" in report.planner_readable_report
            assert "Remaining local uncertainty:" in report.planner_readable_report

        if state.verifier_reports:
            first_verifier = state.verifier_reports[0]
            assert first_verifier.task_understanding
            assert first_verifier.execution_plan
            assert first_verifier.result_summary
            assert first_verifier.remaining_local_uncertainty

        assert "Remaining local uncertainty:" in state.working_memory[0].evidence_summary
        assert any(
            "Task completion:" in entry.evidence_summary
            or "Task was completed only in a capability-limited contracted form" in entry.evidence_summary
            or "baseline S0/S1 run still cannot determine external consistency or final mechanism" in entry.evidence_summary
            or "low-cost baseline S0/S1 run still cannot determine external consistency or final mechanism" in entry.evidence_summary
            or "bounded baseline S0/S1 run still cannot determine external consistency or final mechanism" in entry.evidence_summary
            or "targeted micro follow-up still cannot establish verifier-aligned mechanism selection" in entry.evidence_summary
            or "the evidence cards still need Planner-level synthesis before any mechanism decision"
            in entry.evidence_summary
            for entry in state.working_memory
        )
        assert any(
            "macro task understanding:" in diagnosis or "microscopic execution plan:" in diagnosis
            for diagnosis in state.planner_diagnosis_history
        )
        assert any(
            "planner interpretation of verifier evidence" in diagnosis.lower()
            or "remaining local uncertainty" in diagnosis.lower()
            or "capability assessment" in diagnosis.lower()
            for diagnosis in state.planner_diagnosis_history
        )
        assert any(entry.capability_assessment for entry in state.working_memory)
        assert any(entry.hypothesis_uncertainty_note for entry in state.working_memory)

    bulky_state = states["bulky_rim_case"]
    non_esipt_state = states["non_esipt_hydrocarbon_case"]
    ict_state = states["ict_donor_acceptor_case"]

    assert bulky_state.finalize is True
    assert bulky_state.planner_action_history == ["macro_and_microscopic", "verifier", "finalize"]
    assert bulky_state.current_hypothesis == "restriction of intramolecular motion (RIM)-dominated AIE"
    assert bulky_state.verifier_reports

    assert non_esipt_state.finalize is True
    assert non_esipt_state.planner_action_history == ["macro_and_microscopic", "finalize"]
    assert len(non_esipt_state.working_memory) >= 1
    assert any(
        entry.capability_assessment and "capab" in entry.capability_assessment.lower()
        for entry in non_esipt_state.working_memory
    )

    assert ict_state.finalize is False
    assert "verifier" in ict_state.planner_action_history
    assert "microscopic" in ict_state.planner_action_history
    assert len(ict_state.verifier_reports) >= 1

    assert bulky_state.planner_action_history != non_esipt_state.planner_action_history
    assert bulky_state.planner_action_history != ict_state.planner_action_history
    assert non_esipt_state.working_memory[-1].contraction_reason != ict_state.working_memory[-1].contraction_reason


def test_low_information_case_shows_capability_limited_contraction(
    tmp_path: Path,
    install_specialized_test_doubles,
) -> None:
    install_specialized_test_doubles()
    state = _run_case(MOCK_CASES[1], tmp_path)

    assert state.hypothesis_pool[0].candidate_strength == "medium"
    assert state.planner_action_history[0] == "macro_and_microscopic"
    assert any(action in {"microscopic", "finalize"} for action in state.planner_action_history[1:])
    assert "generic mock fallback" in state.macro_reports[0].task_received.lower()
    assert any(
        entry.contraction_reason
        and (
            "bounded uncertainty" in entry.contraction_reason.lower()
            or "do not use verifier as exploratory search" in entry.contraction_reason.lower()
            or "stopping with bounded uncertainty" in entry.contraction_reason.lower()
        )
        for entry in state.working_memory
    )
    assert any(
        entry.capability_assessment and "capability" in entry.capability_assessment.lower()
        for entry in state.working_memory
    )
    assert state.finalize is True
