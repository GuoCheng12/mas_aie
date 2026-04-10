from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from aie_mas.cli.run_case import (
    LiveRunTracer,
    app,
    build_planner_synthesis_payload,
    build_summary_payload,
    prepare_report_paths,
    run_case_workflow,
)
from aie_mas.config import AieMasConfig


PROMPTS_DIR = Path(__file__).resolve().parents[1] / "src" / "aie_mas" / "prompts"


def _parse_terminal_summary(stdout: str) -> dict[str, str]:
    payload: dict[str, str] = {}
    for raw_line in stdout.strip().splitlines():
        key, value = raw_line.split(": ", 1)
        payload[key] = value
    return payload


def test_minimal_workflow_smoke(tmp_path: Path, install_specialized_test_doubles) -> None:
    install_specialized_test_doubles()
    smiles = "C(c1ccccc1)(c1ccccc1)=C(c1ccccc1)c1ccccc1"
    state = run_case_workflow(
        smiles=smiles,
        user_query="Assess the likely AIE mechanism for this molecule.",
        execution_profile="local-dev",
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
    assert state.long_term_memory_path is None
    assert state.macro_reports[0].task_understanding
    assert state.macro_reports[0].execution_plan
    assert state.macro_reports[0].result_summary
    assert state.microscopic_reports[0].task_understanding
    assert state.microscopic_reports[0].reasoning_summary
    assert state.microscopic_reports[0].execution_plan
    assert state.microscopic_reports[0].task_received != "Run fixed first-stage S0/S1 optimization."
    assert "current working hypothesis" in state.macro_reports[0].task_received
    assert state.finalize is True


def test_run_case_workflow_emits_progress_events_with_round_and_agent(
    tmp_path: Path,
    install_specialized_test_doubles,
) -> None:
    install_specialized_test_doubles()
    events: list[dict[str, object]] = []

    state = run_case_workflow(
        smiles="C(c1ccccc1)(c1ccccc1)=C(c1ccccc1)c1ccccc1",
        user_query="Assess the likely AIE mechanism for this molecule.",
        execution_profile="local-dev",
        data_dir=tmp_path / "data_progress",
        memory_dir=tmp_path / "memory_progress",
        log_dir=tmp_path / "log_progress",
        runtime_dir=tmp_path / "runtime_progress",
        progress_callback=events.append,
    )

    assert state.final_answer is not None
    assert events
    assert events[0]["node"] == "ingest_user_query"
    assert events[0]["round"] == 0
    assert events[0]["agent"] == "system"
    assert any(
        event["node"] == "run_macro" and event["round"] == 1 and event["agent"] == "macro"
        for event in events
    )
    assert any(
        event["node"] == "run_microscopic"
        and event["round"] == 1
        and event["agent"] == "microscopic"
        for event in events
    )
    assert any(
        event["node"] == "planner_diagnosis"
        and event["round"] == 1
        and event["agent"] == "planner"
        for event in events
    )
    assert any(event["node"] == "update_working_memory" and event["agent"] == "memory" for event in events)
    assert any(event["node"] == "run_verifier" and event["agent"] == "verifier" for event in events)
    assert events[-1]["node"] == "final_output"
    assert events[-1]["agent"] == "final"
    assert any(event["phase"] == "end" and event["details"] for event in events)


def test_live_run_tracer_writes_live_trace_and_status_files(
    tmp_path: Path,
    install_specialized_test_doubles,
) -> None:
    install_specialized_test_doubles()
    config = AieMasConfig(
        project_root=tmp_path,
        execution_profile="local-dev",
        data_dir=tmp_path / "data_live",
        memory_dir=tmp_path / "memory_live",
        report_dir=tmp_path / "reports_live",
        log_dir=tmp_path / "log_live",
        runtime_dir=tmp_path / "runtime_live",
    )
    case_id = "livecase123456"
    report_paths = prepare_report_paths(config, case_id)
    tracer = LiveRunTracer(
        report_dir=report_paths["report_dir"],
        case_id=case_id,
        smiles="C(c1ccccc1)(c1ccccc1)=C(c1ccccc1)c1ccccc1",
        user_query="Assess the likely AIE mechanism for this molecule.",
    )

    state = run_case_workflow(
        smiles="C(c1ccccc1)(c1ccccc1)=C(c1ccccc1)c1ccccc1",
        user_query="Assess the likely AIE mechanism for this molecule.",
        execution_profile="local-dev",
        data_dir=config.data_dir,
        memory_dir=config.memory_dir,
        log_dir=config.log_dir,
        runtime_dir=config.runtime_dir,
        report_dir=config.report_dir,
        progress_callback=tracer.handle_event,
    )

    assert state.final_answer is not None
    live_trace_path = report_paths["live_trace_path"]
    live_status_path = report_paths["live_status_path"]

    assert live_trace_path.exists()
    assert live_status_path.exists()

    trace_lines = [json.loads(line) for line in live_trace_path.read_text(encoding="utf-8").splitlines()]
    assert trace_lines
    assert any(
        line["phase"] == "end"
        and line["node"] == "run_microscopic"
        and line["details"].get("task_understanding")
        for line in trace_lines
    )
    assert any(
        line["phase"] == "end"
        and line["node"] == "update_working_memory"
        and line["details"].get("agent_reports")
        for line in trace_lines
    )
    assert any(
        line["phase"] == "probe"
        and line["details"].get("probe_stage") == "reasoning"
        for line in trace_lines
    )

    live_status_text = live_status_path.read_text(encoding="utf-8")
    assert "# Live Run Status" in live_status_text
    assert "## Probe Trace" in live_status_text
    assert "stage=reasoning" in live_status_text
    assert "Round 1 | planner | planner_initial" in live_status_text
    assert "Round 1 | microscopic | run_microscopic" in live_status_text
    assert "result_summary" in live_status_text
    assert "remaining_local_uncertainty" in live_status_text


def test_summary_payload_groups_information_by_round(tmp_path: Path, install_specialized_test_doubles) -> None:
    install_specialized_test_doubles()
    smiles = "C(c1ccccc1)(c1ccccc1)=C(c1ccccc1)c1ccccc1"
    state = run_case_workflow(
        smiles=smiles,
        user_query="Assess the likely AIE mechanism for this molecule.",
        execution_profile="local-dev",
        data_dir=tmp_path / "data_rounds",
        memory_dir=tmp_path / "memory_rounds",
        report_dir=tmp_path / "reports_rounds",
        log_dir=tmp_path / "log_rounds",
        runtime_dir=tmp_path / "runtime_rounds",
    )

    summary_payload = build_summary_payload(state, tmp_path / "reports_rounds" / "example_case")

    assert len(summary_payload["rounds"]) == len(state.working_memory)
    first_round = summary_payload["rounds"][0]
    assert first_round["round_id"] == 1
    assert first_round["action_taken"] == "macro, microscopic"
    assert first_round["planner"]["selected_next_action"] in {"microscopic", "verifier"}
    assert first_round["planner"]["agent_task_instructions"]
    assert first_round["planner"]["hypothesis_uncertainty_note"]
    assert first_round["planner"]["capability_assessment"]
    assert first_round["working_memory"]["main_gap"]
    assert first_round["working_memory"]["agent_reports"]
    assert first_round["working_memory"]["agent_reports"][0]["task_understanding"]
    assert first_round["working_memory"]["agent_reports"][0]["reasoning_summary"]
    assert first_round["working_memory"]["agent_reports"][0]["remaining_local_uncertainty"]
    assert "local_uncertainty_summary" in first_round["working_memory"]

    planner_synthesis = build_planner_synthesis_payload(state)
    assert planner_synthesis["猜想"]["当前结论"] == state.current_hypothesis
    assert planner_synthesis["推理证据"]["关键轮次"]
    assert planner_synthesis["建议"]


def test_cli_writes_report_files_and_prints_concise_summary(
    tmp_path: Path,
    install_specialized_test_doubles,
) -> None:
    install_specialized_test_doubles()
    runner = CliRunner()
    report_dir = tmp_path / "reports_cli"
    result = runner.invoke(
        app,
        [
            "--smiles",
            "C(c1ccccc1)(c1ccccc1)=C(c1ccccc1)c1ccccc1",
            "--execution-profile",
            "local-dev",
            "--disable-long-term-memory",
            "--data-dir",
            str(tmp_path / "data_cli"),
            "--memory-dir",
            str(tmp_path / "memory_cli"),
            "--report-dir",
            str(report_dir),
            "--log-dir",
            str(tmp_path / "log_cli"),
            "--runtime-dir",
            str(tmp_path / "runtime_cli"),
        ],
    )

    assert result.exit_code == 0
    terminal_summary = _parse_terminal_summary(result.stdout)
    summary_path = Path(terminal_summary["summary_file"])
    full_state_path = Path(terminal_summary["full_state_file"])
    planner_synthesis_path = Path(terminal_summary["planner_synthesis_file"])

    assert summary_path.exists()
    assert full_state_path.exists()
    assert planner_synthesis_path.exists()
    assert summary_path.parent.parent == report_dir
    assert terminal_summary["case_id"] == summary_path.parent.name.split("_", 1)[1]

    summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
    full_state_payload = json.loads(full_state_path.read_text(encoding="utf-8"))
    planner_synthesis_payload = json.loads(planner_synthesis_path.read_text(encoding="utf-8"))

    assert summary_payload["case_id"] == terminal_summary["case_id"]
    assert summary_payload["current_hypothesis"] == terminal_summary["current_hypothesis"]
    assert str(summary_payload["confidence"]) == terminal_summary["confidence"]
    assert summary_payload["action"] == terminal_summary["action"]
    assert str(summary_payload["finalize"]) == terminal_summary["finalize"]
    assert str(summary_payload["working_memory_rounds"]) == terminal_summary["rounds"]
    assert summary_payload["hypothesis_uncertainty_note"]
    assert summary_payload["final_hypothesis_rationale"]
    assert summary_payload["capability_assessment"]
    assert summary_payload["report_dir"] == str(summary_path.parent)
    assert terminal_summary["report_dir"] == str(summary_path.parent)
    assert planner_synthesis_payload["case_id"] == summary_payload["case_id"]
    assert planner_synthesis_payload["smiles"] == summary_payload["smiles"]
    assert planner_synthesis_payload["猜想"]["当前结论"] == summary_payload["current_hypothesis"]
    assert planner_synthesis_payload["推理证据"]["关键轮次"]
    assert planner_synthesis_payload["建议"]
    assert len(summary_payload["rounds"]) == summary_payload["working_memory_rounds"]
    assert summary_payload["rounds"][0]["action_taken"] == "macro, microscopic"
    assert summary_payload["rounds"][0]["planner"]["selected_next_action"] in {"microscopic", "verifier"}
    assert summary_payload["rounds"][0]["planner"]["capability_assessment"]
    assert summary_payload["rounds"][0]["working_memory"]["agent_reports"]
    assert summary_payload["rounds"][0]["working_memory"]["agent_reports"][0]["reasoning_summary"]
    assert summary_payload["rounds"][0]["working_memory"]["agent_reports"][0]["remaining_local_uncertainty"]
    assert summary_payload["rounds"][0]["working_memory"]["evidence_summary"]
    assert full_state_payload["runtime_context"]["execution_profile"] == "local-dev"
    assert full_state_payload["runtime_context"]["tool_backend"] == "real"
    assert full_state_payload["runtime_context"]["enable_long_term_memory"] is False
    assert full_state_payload["state_snapshot"]["case_id"] == summary_payload["case_id"]


def test_cli_can_enable_long_term_memory_for_a_run(
    tmp_path: Path,
    install_specialized_test_doubles,
) -> None:
    install_specialized_test_doubles()
    runner = CliRunner()
    memory_dir = tmp_path / "memory_cli_on"
    result = runner.invoke(
        app,
        [
            "--smiles",
            "C(c1ccccc1)(c1ccccc1)=C(c1ccccc1)c1ccccc1",
            "--execution-profile",
            "local-dev",
            "--enable-long-term-memory",
            "--data-dir",
            str(tmp_path / "data_cli_on"),
            "--memory-dir",
            str(memory_dir),
            "--report-dir",
            str(tmp_path / "reports_cli_on"),
            "--log-dir",
            str(tmp_path / "log_cli_on"),
            "--runtime-dir",
            str(tmp_path / "runtime_cli_on"),
        ],
    )

    assert result.exit_code == 0
    terminal_summary = _parse_terminal_summary(result.stdout)
    summary_path = Path(terminal_summary["summary_file"])
    full_state_payload = json.loads(
        Path(terminal_summary["full_state_file"]).read_text(encoding="utf-8")
    )
    summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))

    assert summary_path.exists()
    assert summary_payload["rounds"]
    assert full_state_payload["runtime_context"]["enable_long_term_memory"] is True
    assert (memory_dir / "case_memory.json").exists()


def test_cli_uses_environment_defaults_when_flags_are_omitted(
    tmp_path: Path,
    monkeypatch,
    install_specialized_test_doubles,
) -> None:
    install_specialized_test_doubles()
    runner = CliRunner()
    monkeypatch.setenv("AIE_MAS_EXECUTION_PROFILE", "linux-prod")
    monkeypatch.setenv("AIE_MAS_TOOL_BACKEND", "real")
    monkeypatch.setenv("AIE_MAS_PLANNER_BACKEND", "openai_sdk")
    monkeypatch.setenv("AIE_MAS_ENABLE_LONG_TERM_MEMORY", "1")
    monkeypatch.setenv("AIE_MAS_PROMPTS_DIR", str(PROMPTS_DIR))
    monkeypatch.setenv("AIE_MAS_DATA_DIR", str(tmp_path / "data_env"))
    monkeypatch.setenv("AIE_MAS_MEMORY_DIR", str(tmp_path / "memory_env"))
    monkeypatch.setenv("AIE_MAS_REPORT_DIR", str(tmp_path / "reports_env"))
    monkeypatch.setenv("AIE_MAS_LOG_DIR", str(tmp_path / "log_env"))
    monkeypatch.setenv("AIE_MAS_RUNTIME_DIR", str(tmp_path / "runtime_env"))

    result = runner.invoke(
        app,
        [
            "--smiles",
            "C(c1ccccc1)(c1ccccc1)=C(c1ccccc1)c1ccccc1",
        ],
    )

    assert result.exit_code == 0
    terminal_summary = _parse_terminal_summary(result.stdout)
    summary_payload = json.loads(
        Path(terminal_summary["summary_file"]).read_text(encoding="utf-8")
    )
    full_state_payload = json.loads(
        Path(terminal_summary["full_state_file"]).read_text(encoding="utf-8")
    )

    assert summary_payload["rounds"]
    assert full_state_payload["runtime_context"]["execution_profile"] == "linux-prod"
    assert full_state_payload["runtime_context"]["tool_backend"] == "real"
    assert full_state_payload["runtime_context"]["enable_long_term_memory"] is True
    assert full_state_payload["runtime_context"]["report_dir"] == str(tmp_path / "reports_env")


def test_cli_uses_default_project_report_dir_when_unspecified(
    tmp_path: Path,
    monkeypatch,
    install_specialized_test_doubles,
) -> None:
    install_specialized_test_doubles()
    runner = CliRunner()
    monkeypatch.setenv("AIE_MAS_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("AIE_MAS_EXECUTION_PROFILE", "local-dev")
    monkeypatch.setenv("AIE_MAS_TOOL_BACKEND", "real")
    monkeypatch.setenv("AIE_MAS_PLANNER_BACKEND", "openai_sdk")
    monkeypatch.setenv("AIE_MAS_PROMPTS_DIR", str(PROMPTS_DIR))
    monkeypatch.setenv("AIE_MAS_DATA_DIR", str(tmp_path / "data_default_report"))
    monkeypatch.setenv("AIE_MAS_LOG_DIR", str(tmp_path / "log_default_report"))
    monkeypatch.setenv("AIE_MAS_RUNTIME_DIR", str(tmp_path / "runtime_default_report"))

    result = runner.invoke(
        app,
        [
            "--smiles",
            "C(c1ccccc1)(c1ccccc1)=C(c1ccccc1)c1ccccc1",
        ],
    )

    assert result.exit_code == 0
    terminal_summary = _parse_terminal_summary(result.stdout)
    summary_path = Path(terminal_summary["summary_file"])
    summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
    full_state_payload = json.loads(
        Path(terminal_summary["full_state_file"]).read_text(encoding="utf-8")
    )

    assert summary_path.parent.parent == (tmp_path / "var" / "reports")
    assert summary_payload["rounds"]
    assert full_state_payload["runtime_context"]["report_dir"] == str(tmp_path / "var" / "reports")
