from __future__ import annotations

from aie_mas.agents.result_agents import MicroscopicAgent
from aie_mas.graph.state import MicroscopicTaskSpec


def test_targeted_microscopic_task_interface_is_available(install_specialized_test_doubles) -> None:
    fake_amesp = install_specialized_test_doubles()
    agent = MicroscopicAgent(amesp_tool=fake_amesp)
    task_spec = MicroscopicTaskSpec(
        mode="targeted_follow_up",
        task_label="round-2-targeted",
        objective="Investigate a weak verifier conflict with targeted micro follow-up.",
        target_property="weak_conflict_resolution",
    )

    report = agent.run(
        smiles="C(c1ccccc1)(c1ccccc1)=C(c1ccccc1)c1ccccc1",
        task_received="Assess bounded conformer sensitivity for the unresolved microscopic follow-up.",
        task_spec=task_spec,
        current_hypothesis="restriction of intramolecular motion (RIM)-dominated AIE",
    )

    assert report.task_received == "Assess bounded conformer sensitivity for the unresolved microscopic follow-up."
    assert report.task_understanding
    assert report.reasoning_summary
    assert report.execution_plan
    assert report.result_summary
    assert report.remaining_local_uncertainty
    assert report.task_completion_status == "completed"
    assert "The Planner requested `run_conformer_bundle`." in report.task_completion
    assert "All requested deliverables were produced" in report.task_completion
    assert report.structured_results["task_mode"] == "targeted_follow_up"
    assert report.structured_results["task_label"] == "round-2-targeted"
    assert report.structured_results["task_completion_status"] == "completed"
    assert report.structured_results["execution_plan"]["capability_route"] == "conformer_bundle_follow_up"
    assert report.structured_results["attempted_route"] == "conformer_bundle_follow_up"
    assert report.structured_results["completion_reason_code"] is None
    assert fake_amesp.called is True
    assert report.planner_readable_report.startswith("Task completion:")
    assert "Task understanding:" in report.planner_readable_report
