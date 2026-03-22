from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer

from aie_mas.config import AieMasConfig, ExecutionProfile, PlannerBackend, ToolBackend
from aie_mas.graph.builder import build_graph, invoke_graph
from aie_mas.graph.state import AieMasState

app = typer.Typer(add_completion=False)


def build_runtime_config(
    execution_profile: Optional[ExecutionProfile] = None,
    tool_backend: Optional[ToolBackend] = None,
    enable_long_term_memory: Optional[bool] = None,
    planner_backend: Optional[PlannerBackend] = None,
    planner_base_url: Optional[str] = None,
    planner_model: Optional[str] = None,
    planner_api_key: Optional[str] = None,
    planner_temperature: Optional[float] = None,
    planner_timeout_seconds: Optional[float] = None,
    prompts_dir: Optional[Path] = None,
    data_dir: Optional[Path] = None,
    memory_dir: Optional[Path] = None,
    report_dir: Optional[Path] = None,
    log_dir: Optional[Path] = None,
    runtime_dir: Optional[Path] = None,
    tools_work_dir: Optional[Path] = None,
    atb_binary_path: Optional[Path] = None,
    amesp_binary_path: Optional[Path] = None,
    external_search_binary_path: Optional[Path] = None,
) -> AieMasConfig:
    return AieMasConfig.from_env(
        execution_profile=execution_profile,
        tool_backend=tool_backend,
        enable_long_term_memory=enable_long_term_memory,
        planner_backend=planner_backend,
        planner_base_url=planner_base_url,
        planner_model=planner_model,
        planner_api_key=planner_api_key,
        planner_temperature=planner_temperature,
        planner_timeout_seconds=planner_timeout_seconds,
        prompts_dir=prompts_dir,
        data_dir=data_dir,
        memory_dir=memory_dir,
        report_dir=report_dir,
        log_dir=log_dir,
        runtime_dir=runtime_dir,
        tools_work_dir=tools_work_dir,
        atb_binary_path=atb_binary_path,
        amesp_binary_path=amesp_binary_path,
        external_search_binary_path=external_search_binary_path,
    )


def run_case_workflow(
    smiles: str,
    user_query: str,
    execution_profile: Optional[ExecutionProfile] = None,
    tool_backend: Optional[ToolBackend] = None,
    enable_long_term_memory: Optional[bool] = None,
    planner_backend: Optional[PlannerBackend] = None,
    planner_base_url: Optional[str] = None,
    planner_model: Optional[str] = None,
    planner_api_key: Optional[str] = None,
    planner_temperature: Optional[float] = None,
    planner_timeout_seconds: Optional[float] = None,
    prompts_dir: Optional[Path] = None,
    data_dir: Optional[Path] = None,
    memory_dir: Optional[Path] = None,
    report_dir: Optional[Path] = None,
    log_dir: Optional[Path] = None,
    runtime_dir: Optional[Path] = None,
    tools_work_dir: Optional[Path] = None,
    atb_binary_path: Optional[Path] = None,
    amesp_binary_path: Optional[Path] = None,
    external_search_binary_path: Optional[Path] = None,
) -> AieMasState:
    config = build_runtime_config(
        execution_profile=execution_profile,
        tool_backend=tool_backend,
        enable_long_term_memory=enable_long_term_memory,
        planner_backend=planner_backend,
        planner_base_url=planner_base_url,
        planner_model=planner_model,
        planner_api_key=planner_api_key,
        planner_temperature=planner_temperature,
        planner_timeout_seconds=planner_timeout_seconds,
        prompts_dir=prompts_dir,
        data_dir=data_dir,
        memory_dir=memory_dir,
        report_dir=report_dir,
        log_dir=log_dir,
        runtime_dir=runtime_dir,
        tools_work_dir=tools_work_dir,
        atb_binary_path=atb_binary_path,
        amesp_binary_path=amesp_binary_path,
        external_search_binary_path=external_search_binary_path,
    )
    graph = build_graph(config)
    initial_state = AieMasState(user_query=user_query, smiles=smiles)
    return invoke_graph(graph, initial_state)


@app.command()
def main(
    smiles: str = typer.Option(..., help="Target molecule SMILES."),
    user_query: str = typer.Option(
        "Assess the likely AIE mechanism for this molecule.",
        help="User task description.",
    ),
    execution_profile: Optional[str] = typer.Option(
        None,
        help="Execution profile: local-dev for local mock validation, linux-prod for Linux deployment.",
    ),
    tool_backend: Optional[str] = typer.Option(
        None,
        help="Tool backend: mock for current first-stage runs, real for future Linux wrappers.",
    ),
    enable_long_term_memory: Optional[bool] = typer.Option(
        None,
        "--enable-long-term-memory/--disable-long-term-memory",
        help="Enable or disable long-term memory reads and writes for this run.",
    ),
    planner_backend: Optional[str] = typer.Option(
        None,
        help="Planner backend: mock or openai_sdk.",
    ),
    planner_base_url: Optional[str] = typer.Option(
        None,
        help="OpenAI-compatible planner base URL.",
    ),
    planner_model: Optional[str] = typer.Option(
        None,
        help="OpenAI-compatible planner model name.",
    ),
    planner_api_key: Optional[str] = typer.Option(
        None,
        help="OpenAI-compatible planner API key. Optional for proxies that accept a placeholder.",
    ),
    planner_temperature: Optional[float] = typer.Option(
        None,
        help="Planner LLM temperature.",
    ),
    planner_timeout_seconds: Optional[float] = typer.Option(
        None,
        help="Planner LLM timeout in seconds.",
    ),
    prompts_dir: Optional[Path] = typer.Option(
        None,
        help="Optional prompt directory.",
    ),
    data_dir: Optional[Path] = typer.Option(
        None,
        help="Optional data directory.",
    ),
    memory_dir: Optional[Path] = typer.Option(
        None,
        help="Optional directory for long-term memory JSON files.",
    ),
    report_dir: Optional[Path] = typer.Option(
        None,
        help="Optional directory where per-run report folders will be written.",
    ),
    log_dir: Optional[Path] = typer.Option(
        None,
        help="Optional log directory.",
    ),
    runtime_dir: Optional[Path] = typer.Option(
        None,
        help="Optional runtime working directory.",
    ),
    tools_work_dir: Optional[Path] = typer.Option(
        None,
        help="Optional tools working directory.",
    ),
    atb_binary_path: Optional[Path] = typer.Option(
        None,
        help="Optional aTB binary path for future Linux integration.",
    ),
    amesp_binary_path: Optional[Path] = typer.Option(
        None,
        help="Optional Amesp binary path for future Linux integration.",
    ),
    external_search_binary_path: Optional[Path] = typer.Option(
        None,
        help="Optional external search tool path for future verifier integration.",
    ),
) -> None:
    config = build_runtime_config(
        execution_profile=execution_profile,
        tool_backend=tool_backend,
        enable_long_term_memory=enable_long_term_memory,
        planner_backend=planner_backend,
        planner_base_url=planner_base_url,
        planner_model=planner_model,
        planner_api_key=planner_api_key,
        planner_temperature=planner_temperature,
        planner_timeout_seconds=planner_timeout_seconds,
        prompts_dir=prompts_dir,
        data_dir=data_dir,
        memory_dir=memory_dir,
        report_dir=report_dir,
        log_dir=log_dir,
        runtime_dir=runtime_dir,
        tools_work_dir=tools_work_dir,
        atb_binary_path=atb_binary_path,
        amesp_binary_path=amesp_binary_path,
        external_search_binary_path=external_search_binary_path,
    )
    graph = build_graph(config)
    state = invoke_graph(graph, AieMasState(user_query=user_query, smiles=smiles))
    report_paths = write_run_report(config, state)
    payload = {
        "runtime_context": config.runtime_context(),
        "summary": build_summary_payload(state, report_paths["report_dir"]),
        "state_snapshot": state.state_snapshot,
    }
    render_terminal_summary(payload["summary"], report_paths)


def build_summary_payload(state: AieMasState, report_dir: Path) -> dict[str, object]:
    final_answer = state.final_answer or {}
    return {
        "case_id": state.case_id,
        "smiles": state.smiles,
        "current_hypothesis": state.current_hypothesis,
        "confidence": state.confidence,
        "diagnosis": final_answer.get("diagnosis"),
        "action": final_answer.get("action"),
        "finalize": state.finalize,
        "hypothesis_uncertainty_note": final_answer.get("hypothesis_uncertainty_note"),
        "capability_assessment": final_answer.get("capability_assessment"),
        "stagnation_assessment": final_answer.get("stagnation_assessment"),
        "contraction_reason": final_answer.get("contraction_reason"),
        "working_memory_rounds": len(state.working_memory),
        "rounds": build_rounds_payload(state),
        "report_dir": str(report_dir),
    }


def build_rounds_payload(state: AieMasState) -> list[dict[str, object]]:
    rounds: list[dict[str, object]] = []
    for entry in state.working_memory:
        rounds.append(
            {
                "round_id": entry.round_id,
                "current_hypothesis": entry.current_hypothesis,
                "confidence": entry.confidence,
                "action_taken": entry.action_taken,
                "planner": {
                    "diagnosis_summary": entry.diagnosis_summary,
                    "selected_next_action": entry.next_action,
                    "task_instruction": entry.planner_task_instruction,
                    "agent_task_instructions": entry.planner_agent_task_instructions,
                    "hypothesis_uncertainty_note": entry.hypothesis_uncertainty_note,
                    "capability_assessment": entry.capability_assessment,
                    "stagnation_assessment": entry.stagnation_assessment,
                    "contraction_reason": entry.contraction_reason,
                },
                "working_memory": {
                    "evidence_summary": entry.evidence_summary,
                    "main_gap": entry.main_gap,
                    "conflict_status": entry.conflict_status,
                    "information_gain_assessment": entry.information_gain_assessment,
                    "gap_trend": entry.gap_trend,
                    "stagnation_detected": entry.stagnation_detected,
                    "local_uncertainty_summary": entry.local_uncertainty_summary,
                    "repeated_local_uncertainty_signals": entry.repeated_local_uncertainty_signals,
                    "capability_lesson_candidates": [
                        lesson.model_dump(mode="json") for lesson in entry.capability_lesson_candidates
                    ],
                    "agent_reports": [
                        agent_entry.model_dump(mode="json") for agent_entry in entry.agent_reports
                    ],
                },
            }
        )
    return rounds


def build_full_state_payload(
    config: AieMasConfig,
    state: AieMasState,
    report_dir: Path,
) -> dict[str, object]:
    return {
        "runtime_context": config.runtime_context(),
        "report_dir": str(report_dir),
        "state_snapshot": state.state_snapshot,
    }


def write_run_report(config: AieMasConfig, state: AieMasState) -> dict[str, Path]:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    case_id = state.case_id or "unknown-case"
    report_dir = config.report_dir / f"{timestamp}_{case_id}"
    report_dir.mkdir(parents=True, exist_ok=True)

    summary_path = report_dir / "summary.json"
    full_state_path = report_dir / "full_state.json"
    summary_payload = build_summary_payload(state, report_dir)
    full_state_payload = build_full_state_payload(config, state, report_dir)

    summary_path.write_text(
        json.dumps(summary_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    full_state_path.write_text(
        json.dumps(full_state_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "report_dir": report_dir,
        "summary_path": summary_path,
        "full_state_path": full_state_path,
    }


def render_terminal_summary(
    summary: dict[str, object],
    report_paths: dict[str, Path],
) -> None:
    lines = [
        f"case_id: {summary['case_id']}",
        f"current_hypothesis: {summary['current_hypothesis']}",
        f"confidence: {summary['confidence']}",
        f"action: {summary['action']}",
        f"finalize: {summary['finalize']}",
        f"rounds: {summary['working_memory_rounds']}",
        f"report_dir: {summary['report_dir']}",
        f"summary_file: {report_paths['summary_path']}",
        f"full_state_file: {report_paths['full_state_path']}",
    ]
    typer.echo("\n".join(lines))


def cli() -> None:
    app()


if __name__ == "__main__":
    cli()
