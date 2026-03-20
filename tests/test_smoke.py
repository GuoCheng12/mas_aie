from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from aie_mas.cli.run_case import app, run_case_workflow


def test_minimal_workflow_smoke(tmp_path: Path) -> None:
    smiles = "C(c1ccccc1)(c1ccccc1)=C(c1ccccc1)c1ccccc1"
    state = run_case_workflow(
        smiles=smiles,
        user_query="Assess the likely AIE mechanism for this molecule.",
        execution_profile="local-dev",
        tool_backend="mock",
        data_dir=tmp_path / "data",
        memory_dir=tmp_path / "memory",
        log_dir=tmp_path / "log",
        runtime_dir=tmp_path / "runtime",
    )

    assert state.current_hypothesis is not None
    assert state.final_answer is not None
    assert state.state_snapshot is not None
    assert len(state.macro_reports) >= 1
    assert len(state.microscopic_reports) >= 1
    assert len(state.verifier_reports) >= 1
    assert len(state.working_memory) >= 2
    assert state.working_memory[0].action_taken == "macro, microscopic"
    assert state.finalize is True


def test_cli_outputs_state_snapshot(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "--smiles",
            "C(c1ccccc1)(c1ccccc1)=C(c1ccccc1)c1ccccc1",
            "--execution-profile",
            "local-dev",
            "--tool-backend",
            "mock",
            "--data-dir",
            str(tmp_path / "data_cli"),
            "--memory-dir",
            str(tmp_path / "memory_cli"),
            "--log-dir",
            str(tmp_path / "log_cli"),
            "--runtime-dir",
            str(tmp_path / "runtime_cli"),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["runtime_context"]["execution_profile"] == "local-dev"
    assert payload["runtime_context"]["tool_backend"] == "mock"
    assert '"state_snapshot"' in result.stdout
    assert '"final_answer"' in result.stdout
