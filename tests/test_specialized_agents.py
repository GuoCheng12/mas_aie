from __future__ import annotations

from aie_mas.agents.result_agents import MacroAgent, VerifierAgent


def test_macro_agent_returns_specialized_local_report() -> None:
    agent = MacroAgent()
    report = agent.run(
        smiles="C(c1ccccc1)(c1ccccc1)=C(c1ccccc1)c1ccccc1",
        task_received=(
            "Assess macro-level structural evidence relevant to the current working hypothesis "
            "'restriction of intramolecular motion (RIM)-dominated AIE'. Summarize low-cost structural indicators only."
        ),
        current_hypothesis="restriction of intramolecular motion (RIM)-dominated AIE",
    )

    assert report.task_understanding
    assert report.execution_plan
    assert report.result_summary
    assert report.remaining_local_uncertainty
    assert report.structured_results["aromatic_atom_count"] >= 1
    assert "global mechanism judgment" in report.task_understanding
    assert "Task understanding:" in report.planner_readable_report


def test_verifier_agent_returns_specialized_local_report() -> None:
    agent = VerifierAgent()
    report = agent.run(
        smiles="C(c1ccccc1)(c1ccccc1)=C(c1ccccc1)c1ccccc1",
        current_hypothesis="restriction of intramolecular motion (RIM)-dominated AIE",
        task_received=(
            "Retrieve external supervision evidence for the current working hypothesis "
            "'restriction of intramolecular motion (RIM)-dominated AIE' and clarify the current gap."
        ),
    )

    assert report.task_understanding
    assert report.execution_plan
    assert report.result_summary
    assert report.remaining_local_uncertainty
    assert report.structured_results["source_count"] >= 1
    assert report.structured_results["evidence_cards"]
    assert "topic_tags" in report.structured_results["evidence_cards"][0]
    assert "Task understanding:" in report.planner_readable_report
