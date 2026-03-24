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
        task_received=task_spec.objective,
        task_spec=task_spec,
        current_hypothesis="restriction of intramolecular motion (RIM)-dominated AIE",
    )

    assert report.task_received == task_spec.objective
    assert report.task_understanding
    assert report.reasoning_summary
    assert report.execution_plan
    assert report.result_summary
    assert report.remaining_local_uncertainty
    assert report.task_completion_status == "partial"
    assert "targeted microscopic follow-up could not be executed" in report.task_completion
    assert report.structured_results["task_mode"] == "targeted_follow_up"
    assert report.structured_results["task_label"] == "round-2-targeted"
    assert report.structured_results["task_completion_status"] == "partial"
    assert "targeted microscopic follow-up beyond the current Amesp baseline workflow" in " ".join(
        report.structured_results["unsupported_requests"]
    )
    assert fake_amesp.called is True
    assert report.planner_readable_report.startswith("Task completion:")
    assert "Task understanding:" in report.planner_readable_report
