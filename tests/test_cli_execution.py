from __future__ import annotations

import json
import subprocess
from pathlib import Path

from aie_mas.config import AieMasConfig
from aie_mas.graph.state import (
    MacroExecutionPlan,
    MicroscopicExecutionPlan,
    MicroscopicToolPlan,
    MicroscopicToolRequest,
)
from aie_mas.tools.cli_execution import MacroCliExecutionTool, MicroscopicCliExecutionTool


def test_macro_cli_execution_tool_invokes_cli(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def _fake_run(cmd, *, input, capture_output, text, cwd, env, timeout, check):
        captured["cmd"] = cmd
        captured["input"] = json.loads(input)
        captured["cwd"] = cwd
        captured["timeout"] = timeout
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=json.dumps(
                {
                    "executed_capability": "screen_donor_acceptor_layout",
                    "selected_capability": "screen_donor_acceptor_layout",
                    "requested_capability": "screen_donor_acceptor_layout",
                    "performed_new_calculations": False,
                    "reused_existing_artifacts": False,
                    "covered_observable_tags": ["donor_acceptor_layout", "conjugation_summary"],
                    "missing_deliverables": [],
                    "resolved_target_ids": {"structure_source": "smiles_only_fallback"},
                    "planner_requested_capability": "screen_donor_acceptor_layout",
                    "translation_substituted_action": False,
                    "translation_substitution_reason": "",
                    "fulfillment_mode": "exact",
                }
            ),
            stderr="",
        )

    monkeypatch.setattr("aie_mas.tools.cli_execution.subprocess.run", _fake_run)
    tool = MacroCliExecutionTool(AieMasConfig(project_root=tmp_path))

    result = tool.execute(
        plan=MacroExecutionPlan(
            local_goal="screen donor acceptor",
            structure_source="smiles_only_fallback",
            selected_capability="screen_donor_acceptor_layout",
        ),
        smiles="c1ccccc1",
        shared_structure_context=None,
    )

    assert captured["cmd"][1:] == ["-m", "aie_mas.cli.macro_exec"]
    assert captured["input"]["smiles"] == "c1ccccc1"
    assert captured["input"]["plan"]["selected_capability"] == "screen_donor_acceptor_layout"
    assert result["executed_capability"] == "screen_donor_acceptor_layout"


def test_microscopic_cli_execution_tool_invokes_cli(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def _fake_run(cmd, *, input, capture_output, text, cwd, env, timeout, check):
        captured["cmd"] = cmd
        captured["input"] = json.loads(input)
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=json.dumps(
                {
                    "route": "artifact_parse_only",
                    "executed_capability": "extract_ct_descriptors_from_bundle",
                    "performed_new_calculations": False,
                    "reused_existing_artifacts": True,
                    "requested_capability": "extract_ct_descriptors_from_bundle",
                    "resolved_target_ids": {"artifact_bundle_id": "round_01_baseline_bundle"},
                    "honored_constraints": [],
                    "unmet_constraints": [],
                    "missing_deliverables": [],
                    "structure": None,
                    "s0": None,
                    "s1": None,
                    "parsed_snapshot_records": [],
                    "route_records": [],
                    "route_summary": {"artifact_scope": "baseline_bundle"},
                    "raw_step_results": {},
                    "generated_artifacts": {},
                }
            ),
            stderr="",
        )

    monkeypatch.setattr("aie_mas.tools.cli_execution.subprocess.run", _fake_run)
    tool = MicroscopicCliExecutionTool(AieMasConfig(project_root=tmp_path))
    plan = MicroscopicExecutionPlan(
        local_goal="parse CT descriptors",
        structure_source="existing_prepared_structure",
        failure_reporting="return local failure",
        microscopic_tool_plan=MicroscopicToolPlan(),
        microscopic_tool_request=MicroscopicToolRequest(
            capability_name="extract_ct_descriptors_from_bundle",
            reuse_existing_artifacts_only=True,
            artifact_bundle_id="round_01_baseline_bundle",
            artifact_kind="baseline_bundle",
            requested_route_summary="parse existing bundle",
        ),
    )

    result = tool.execute(
        plan=plan,
        smiles="c1ccccc1",
        label="case_round_01_micro",
        workdir=tmp_path / "work",
        available_artifacts={"artifact_bundle_registry_entries": []},
        round_index=1,
        case_id="case",
        current_hypothesis="ICT",
    )

    assert captured["cmd"][1:] == ["-m", "aie_mas.cli.microscopic_exec"]
    assert captured["input"]["microscopic_tool_request"]["capability_name"] == "extract_ct_descriptors_from_bundle"
    assert captured["input"]["tool_config"]["amesp_bin"] is None
    assert result.executed_capability == "extract_ct_descriptors_from_bundle"
    assert result.reused_existing_artifacts is True


def test_microscopic_cli_execution_tool_can_wrap_baseline_capability(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def _fake_run(cmd, *, input, capture_output, text, cwd, env, timeout, check):
        captured["input"] = json.loads(input)
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=json.dumps(
                {
                    "route": "baseline_bundle",
                    "executed_capability": "run_baseline_bundle",
                    "performed_new_calculations": True,
                    "reused_existing_artifacts": False,
                    "requested_capability": "run_baseline_bundle",
                    "resolved_target_ids": {},
                    "honored_constraints": [],
                    "unmet_constraints": [],
                    "missing_deliverables": [],
                    "structure": None,
                    "s0": None,
                    "s1": None,
                    "parsed_snapshot_records": [],
                    "route_records": [],
                    "route_summary": {},
                    "raw_step_results": {},
                    "generated_artifacts": {},
                }
            ),
            stderr="",
        )

    monkeypatch.setattr("aie_mas.tools.cli_execution.subprocess.run", _fake_run)
    tool = MicroscopicCliExecutionTool(AieMasConfig(project_root=tmp_path))
    plan = MicroscopicExecutionPlan(
        local_goal="run baseline",
        structure_source="prepared_from_smiles",
        failure_reporting="return local failure",
        microscopic_tool_plan=MicroscopicToolPlan(),
        microscopic_tool_request=MicroscopicToolRequest(
            capability_name="run_baseline_bundle",
            perform_new_calculation=True,
            requested_route_summary="baseline run",
        ),
    )

    result = tool.execute(
        plan=plan,
        smiles="c1ccccc1",
        label="case_round_01_micro",
        workdir=tmp_path / "work",
        available_artifacts={},
        round_index=1,
        case_id="case",
        current_hypothesis="ICT",
    )

    assert captured["input"]["microscopic_tool_request"]["capability_name"] == "run_baseline_bundle"
    assert captured["input"]["requested_deliverables"] == []
    assert result.executed_capability == "run_baseline_bundle"
    assert result.performed_new_calculations is True
