from __future__ import annotations

from dataclasses import dataclass
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import typer

from aie_mas.config import (
    AieMasConfig,
    ExecutionProfile,
    MacroBackend,
    MicroscopicBackend,
    PlannerBackend,
    ToolBackend,
    VerifierBackend,
)
from aie_mas.graph.builder import build_graph, invoke_graph
from aie_mas.graph.state import AieMasState, WorkflowProgressEvent

app = typer.Typer(add_completion=False)


@dataclass(frozen=True)
class WorkflowRunArtifacts:
    state: AieMasState
    report_paths: dict[str, Path]
    runtime_context: dict[str, object]


class WorkflowRunFailed(RuntimeError):
    def __init__(
        self,
        cause: Exception,
        *,
        case_id: str,
        report_paths: dict[str, Path],
    ) -> None:
        super().__init__(f"{type(cause).__name__}: {cause}")
        self.cause = cause
        self.case_id = case_id
        self.report_paths = report_paths


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
    macro_backend: Optional[MacroBackend] = None,
    macro_base_url: Optional[str] = None,
    macro_model: Optional[str] = None,
    macro_api_key: Optional[str] = None,
    macro_temperature: Optional[float] = None,
    macro_timeout_seconds: Optional[float] = None,
    verifier_backend: Optional[VerifierBackend] = None,
    verifier_base_url: Optional[str] = None,
    verifier_model: Optional[str] = None,
    verifier_api_key: Optional[str] = None,
    verifier_temperature: Optional[float] = None,
    verifier_timeout_seconds: Optional[float] = None,
    microscopic_backend: Optional[MicroscopicBackend] = None,
    microscopic_base_url: Optional[str] = None,
    microscopic_model: Optional[str] = None,
    microscopic_api_key: Optional[str] = None,
    microscopic_temperature: Optional[float] = None,
    microscopic_timeout_seconds: Optional[float] = None,
    amesp_npara: Optional[int] = None,
    amesp_maxcore_mb: Optional[int] = None,
    amesp_use_ricosx: Optional[bool] = None,
    amesp_s1_nstates: Optional[int] = None,
    amesp_td_tout: Optional[int] = None,
    amesp_probe_interval_seconds: Optional[float] = None,
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
        macro_backend=macro_backend,
        macro_base_url=macro_base_url,
        macro_model=macro_model,
        macro_api_key=macro_api_key,
        macro_temperature=macro_temperature,
        macro_timeout_seconds=macro_timeout_seconds,
        verifier_backend=verifier_backend,
        verifier_base_url=verifier_base_url,
        verifier_model=verifier_model,
        verifier_api_key=verifier_api_key,
        verifier_temperature=verifier_temperature,
        verifier_timeout_seconds=verifier_timeout_seconds,
        microscopic_backend=microscopic_backend,
        microscopic_base_url=microscopic_base_url,
        microscopic_model=microscopic_model,
        microscopic_api_key=microscopic_api_key,
        microscopic_temperature=microscopic_temperature,
        microscopic_timeout_seconds=microscopic_timeout_seconds,
        amesp_npara=amesp_npara,
        amesp_maxcore_mb=amesp_maxcore_mb,
        amesp_use_ricosx=amesp_use_ricosx,
        amesp_s1_nstates=amesp_s1_nstates,
        amesp_td_tout=amesp_td_tout,
        amesp_probe_interval_seconds=amesp_probe_interval_seconds,
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
    macro_backend: Optional[MacroBackend] = None,
    macro_base_url: Optional[str] = None,
    macro_model: Optional[str] = None,
    macro_api_key: Optional[str] = None,
    macro_temperature: Optional[float] = None,
    macro_timeout_seconds: Optional[float] = None,
    verifier_backend: Optional[VerifierBackend] = None,
    verifier_base_url: Optional[str] = None,
    verifier_model: Optional[str] = None,
    verifier_api_key: Optional[str] = None,
    verifier_temperature: Optional[float] = None,
    verifier_timeout_seconds: Optional[float] = None,
    microscopic_backend: Optional[MicroscopicBackend] = None,
    microscopic_base_url: Optional[str] = None,
    microscopic_model: Optional[str] = None,
    microscopic_api_key: Optional[str] = None,
    microscopic_temperature: Optional[float] = None,
    microscopic_timeout_seconds: Optional[float] = None,
    amesp_npara: Optional[int] = None,
    amesp_maxcore_mb: Optional[int] = None,
    amesp_use_ricosx: Optional[bool] = None,
    amesp_s1_nstates: Optional[int] = None,
    amesp_td_tout: Optional[int] = None,
    amesp_probe_interval_seconds: Optional[float] = None,
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
    progress_callback: Optional[Callable[[WorkflowProgressEvent], None]] = None,
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
        macro_backend=macro_backend,
        macro_base_url=macro_base_url,
        macro_model=macro_model,
        macro_api_key=macro_api_key,
        macro_temperature=macro_temperature,
        macro_timeout_seconds=macro_timeout_seconds,
        verifier_backend=verifier_backend,
        verifier_base_url=verifier_base_url,
        verifier_model=verifier_model,
        verifier_api_key=verifier_api_key,
        verifier_temperature=verifier_temperature,
        verifier_timeout_seconds=verifier_timeout_seconds,
        microscopic_backend=microscopic_backend,
        microscopic_base_url=microscopic_base_url,
        microscopic_model=microscopic_model,
        microscopic_api_key=microscopic_api_key,
        microscopic_temperature=microscopic_temperature,
        microscopic_timeout_seconds=microscopic_timeout_seconds,
        amesp_npara=amesp_npara,
        amesp_maxcore_mb=amesp_maxcore_mb,
        amesp_use_ricosx=amesp_use_ricosx,
        amesp_s1_nstates=amesp_s1_nstates,
        amesp_td_tout=amesp_td_tout,
        amesp_probe_interval_seconds=amesp_probe_interval_seconds,
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
    graph = build_graph(config, progress_callback=progress_callback)
    initial_state = AieMasState(user_query=user_query, smiles=smiles)
    return invoke_graph(graph, initial_state)


def run_case_workflow_with_reporting(
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
    macro_backend: Optional[MacroBackend] = None,
    macro_base_url: Optional[str] = None,
    macro_model: Optional[str] = None,
    macro_api_key: Optional[str] = None,
    macro_temperature: Optional[float] = None,
    macro_timeout_seconds: Optional[float] = None,
    verifier_backend: Optional[VerifierBackend] = None,
    verifier_base_url: Optional[str] = None,
    verifier_model: Optional[str] = None,
    verifier_api_key: Optional[str] = None,
    verifier_temperature: Optional[float] = None,
    verifier_timeout_seconds: Optional[float] = None,
    microscopic_backend: Optional[MicroscopicBackend] = None,
    microscopic_base_url: Optional[str] = None,
    microscopic_model: Optional[str] = None,
    microscopic_api_key: Optional[str] = None,
    microscopic_temperature: Optional[float] = None,
    microscopic_timeout_seconds: Optional[float] = None,
    amesp_npara: Optional[int] = None,
    amesp_maxcore_mb: Optional[int] = None,
    amesp_use_ricosx: Optional[bool] = None,
    amesp_s1_nstates: Optional[int] = None,
    amesp_td_tout: Optional[int] = None,
    amesp_probe_interval_seconds: Optional[float] = None,
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
    show_progress: bool = True,
    progress_callback: Optional[Callable[[WorkflowProgressEvent], None]] = None,
) -> WorkflowRunArtifacts:
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
        macro_backend=macro_backend,
        macro_base_url=macro_base_url,
        macro_model=macro_model,
        macro_api_key=macro_api_key,
        macro_temperature=macro_temperature,
        macro_timeout_seconds=macro_timeout_seconds,
        verifier_backend=verifier_backend,
        verifier_base_url=verifier_base_url,
        verifier_model=verifier_model,
        verifier_api_key=verifier_api_key,
        verifier_temperature=verifier_temperature,
        verifier_timeout_seconds=verifier_timeout_seconds,
        microscopic_backend=microscopic_backend,
        microscopic_base_url=microscopic_base_url,
        microscopic_model=microscopic_model,
        microscopic_api_key=microscopic_api_key,
        microscopic_temperature=microscopic_temperature,
        microscopic_timeout_seconds=microscopic_timeout_seconds,
        amesp_npara=amesp_npara,
        amesp_maxcore_mb=amesp_maxcore_mb,
        amesp_use_ricosx=amesp_use_ricosx,
        amesp_s1_nstates=amesp_s1_nstates,
        amesp_td_tout=amesp_td_tout,
        amesp_probe_interval_seconds=amesp_probe_interval_seconds,
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
    case_id = uuid.uuid4().hex[:12]
    report_paths = prepare_report_paths(config, case_id)
    tracer = LiveRunTracer(
        report_dir=report_paths["report_dir"],
        case_id=case_id,
        smiles=smiles,
        user_query=user_query,
    )
    progress_callback = compose_progress_callbacks(
        render_progress_event if show_progress and sys.stderr.isatty() else None,
        tracer.handle_event,
        progress_callback,
    )
    graph = build_graph(config, progress_callback=progress_callback)
    initial_state = AieMasState(case_id=case_id, user_query=user_query, smiles=smiles)
    try:
        state = invoke_graph(graph, initial_state)
    except Exception as exc:
        (report_paths["report_dir"] / "workflow_error.json").write_text(
            json.dumps(
                {
                    "case_id": case_id,
                    "smiles": smiles,
                    "user_query": user_query,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "report_dir": str(report_paths["report_dir"]),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        raise WorkflowRunFailed(exc, case_id=case_id, report_paths=report_paths) from exc
    report_paths = write_run_report(config, state, report_paths=report_paths)
    return WorkflowRunArtifacts(
        state=state,
        report_paths=report_paths,
        runtime_context=config.runtime_context(),
    )


@app.command()
def main(
    smiles: str = typer.Option(..., help="Target molecule SMILES."),
    user_query: str = typer.Option(
        "Assess the likely AIE mechanism for this molecule.",
        help="User task description.",
    ),
    execution_profile: Optional[str] = typer.Option(
        None,
        help="Execution profile: local-dev for local validation, linux-prod for Linux deployment.",
    ),
    tool_backend: Optional[str] = typer.Option(
        None,
        help="Tool backend: real.",
    ),
    enable_long_term_memory: Optional[bool] = typer.Option(
        None,
        "--enable-long-term-memory/--disable-long-term-memory",
        help="Enable or disable long-term memory reads and writes for this run.",
    ),
    planner_backend: Optional[str] = typer.Option(
        None,
        help="Planner backend: openai_sdk.",
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
    macro_backend: Optional[str] = typer.Option(
        None,
        help="Macro reasoning backend: openai_sdk.",
    ),
    macro_base_url: Optional[str] = typer.Option(
        None,
        help="OpenAI-compatible macro base URL.",
    ),
    macro_model: Optional[str] = typer.Option(
        None,
        help="OpenAI-compatible macro model name.",
    ),
    macro_api_key: Optional[str] = typer.Option(
        None,
        help="OpenAI-compatible macro API key.",
    ),
    macro_temperature: Optional[float] = typer.Option(
        None,
        help="Macro LLM temperature.",
    ),
    macro_timeout_seconds: Optional[float] = typer.Option(
        None,
        help="Macro LLM timeout in seconds.",
    ),
    verifier_backend: Optional[str] = typer.Option(
        None,
        help="Verifier retrieval backend: openai_sdk.",
    ),
    verifier_base_url: Optional[str] = typer.Option(
        None,
        help="OpenAI-compatible verifier base URL.",
    ),
    verifier_model: Optional[str] = typer.Option(
        None,
        help="OpenAI-compatible verifier model name.",
    ),
    verifier_api_key: Optional[str] = typer.Option(
        None,
        help="OpenAI-compatible verifier API key.",
    ),
    verifier_temperature: Optional[float] = typer.Option(
        None,
        help="Verifier LLM temperature.",
    ),
    verifier_timeout_seconds: Optional[float] = typer.Option(
        None,
        help="Verifier LLM timeout in seconds.",
    ),
    microscopic_backend: Optional[str] = typer.Option(
        None,
        help="Microscopic reasoning backend: openai_sdk.",
    ),
    microscopic_base_url: Optional[str] = typer.Option(
        None,
        help="OpenAI-compatible microscopic base URL.",
    ),
    microscopic_model: Optional[str] = typer.Option(
        None,
        help="OpenAI-compatible microscopic model name.",
    ),
    microscopic_api_key: Optional[str] = typer.Option(
        None,
        help="OpenAI-compatible microscopic API key.",
    ),
    microscopic_temperature: Optional[float] = typer.Option(
        None,
        help="Microscopic LLM temperature.",
    ),
    microscopic_timeout_seconds: Optional[float] = typer.Option(
        None,
        help="Microscopic LLM timeout in seconds.",
    ),
    amesp_npara: Optional[int] = typer.Option(
        None,
        help="CPU parallelism written to %% npara for the real Amesp baseline workflow.",
    ),
    amesp_maxcore_mb: Optional[int] = typer.Option(
        None,
        help="Core memory in MB written to %% maxcore for the real Amesp baseline workflow.",
    ),
    amesp_use_ricosx: Optional[bool] = typer.Option(
        None,
        "--amesp-use-ricosx/--amesp-disable-ricosx",
        help="Enable or disable RICOSX acceleration for the real Amesp baseline workflow.",
    ),
    amesp_s1_nstates: Optional[int] = typer.Option(
        None,
        help="Number of singlet excited states requested in the baseline S1 TD calculation.",
    ),
    amesp_td_tout: Optional[int] = typer.Option(
        None,
        help="TD output threshold written to the Amesp posthf block.",
    ),
    amesp_probe_interval_seconds: Optional[float] = typer.Option(
        None,
        help="Seconds between live microscopic Amesp subprocess heartbeat events.",
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
    show_progress: bool = typer.Option(
        True,
        "--show-progress/--hide-progress",
        help="Print live workflow progress with round and agent information.",
    ),
) -> None:
    run_result = run_case_workflow_with_reporting(
        smiles=smiles,
        user_query=user_query,
        execution_profile=execution_profile,
        tool_backend=tool_backend,
        enable_long_term_memory=enable_long_term_memory,
        planner_backend=planner_backend,
        planner_base_url=planner_base_url,
        planner_model=planner_model,
        planner_api_key=planner_api_key,
        planner_temperature=planner_temperature,
        planner_timeout_seconds=planner_timeout_seconds,
        macro_backend=macro_backend,  # type: ignore[arg-type]
        macro_base_url=macro_base_url,
        macro_model=macro_model,
        macro_api_key=macro_api_key,
        macro_temperature=macro_temperature,
        macro_timeout_seconds=macro_timeout_seconds,
        verifier_backend=verifier_backend,  # type: ignore[arg-type]
        verifier_base_url=verifier_base_url,
        verifier_model=verifier_model,
        verifier_api_key=verifier_api_key,
        verifier_temperature=verifier_temperature,
        verifier_timeout_seconds=verifier_timeout_seconds,
        microscopic_backend=microscopic_backend,
        microscopic_base_url=microscopic_base_url,
        microscopic_model=microscopic_model,
        microscopic_api_key=microscopic_api_key,
        microscopic_temperature=microscopic_temperature,
        microscopic_timeout_seconds=microscopic_timeout_seconds,
        amesp_npara=amesp_npara,
        amesp_maxcore_mb=amesp_maxcore_mb,
        amesp_use_ricosx=amesp_use_ricosx,
        amesp_s1_nstates=amesp_s1_nstates,
        amesp_td_tout=amesp_td_tout,
        amesp_probe_interval_seconds=amesp_probe_interval_seconds,
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
        show_progress=show_progress,
    )
    state = run_result.state
    report_paths = run_result.report_paths
    payload = {
        "runtime_context": run_result.runtime_context,
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
        "final_hypothesis_rationale": final_answer.get("final_hypothesis_rationale"),
        "capability_assessment": final_answer.get("capability_assessment"),
        "stagnation_assessment": final_answer.get("stagnation_assessment"),
        "contraction_reason": final_answer.get("contraction_reason"),
        "molecule_identity_status": final_answer.get("molecule_identity_status"),
        "molecule_identity_context": final_answer.get("molecule_identity_context"),
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
                    "final_hypothesis_rationale": entry.final_hypothesis_rationale,
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


def prepare_report_paths(config: AieMasConfig, case_id: str) -> dict[str, Path]:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    report_dir = config.report_dir / f"{timestamp}_{case_id}"
    report_dir.mkdir(parents=True, exist_ok=True)
    return {
        "report_dir": report_dir,
        "summary_path": report_dir / "summary.json",
        "full_state_path": report_dir / "full_state.json",
        "live_trace_path": report_dir / "live_trace.jsonl",
        "live_status_path": report_dir / "live_status.md",
    }


def write_run_report(
    config: AieMasConfig,
    state: AieMasState,
    report_paths: Optional[dict[str, Path]] = None,
) -> dict[str, Path]:
    if report_paths is None:
        report_paths = prepare_report_paths(config, state.case_id or "unknown-case")
    report_dir = report_paths["report_dir"]
    summary_path = report_paths["summary_path"]
    full_state_path = report_paths["full_state_path"]
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
        **report_paths,
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
        f"live_trace_file: {report_paths['live_trace_path']}",
        f"live_status_file: {report_paths['live_status_path']}",
        f"summary_file: {report_paths['summary_path']}",
        f"full_state_file: {report_paths['full_state_path']}",
    ]
    typer.echo("\n".join(lines))


def render_progress_event(event: WorkflowProgressEvent) -> None:
    round_label = "setup" if event["round"] == 0 else str(event["round"])
    parts = [
        "progress",
        f"phase={event['phase']}",
        f"round={round_label}",
        f"agent={event['agent']}",
        f"node={event['node']}",
    ]
    if event.get("case_id"):
        parts.append(f"case_id={event['case_id']}")
    if event["phase"] == "probe":
        probe_stage = event["details"].get("probe_stage")
        probe_status = event["details"].get("probe_status")
        if probe_stage:
            parts.append(f"stage={probe_stage}")
        if probe_status:
            parts.append(f"status={probe_status}")
        if probe_status == "running":
            if event["details"].get("elapsed_seconds") is not None:
                parts.append(f"elapsed={event['details']['elapsed_seconds']}s")
            if event["details"].get("aop_size_bytes") is not None:
                parts.append(f"aop_bytes={event['details']['aop_size_bytes']}")
            if event["details"].get("pid") is not None:
                parts.append(f"pid={event['details']['pid']}")
    typer.echo(" ".join(parts), err=True)


def compose_progress_callbacks(
    *callbacks: Optional[Callable[[WorkflowProgressEvent], None]],
) -> Optional[Callable[[WorkflowProgressEvent], None]]:
    active_callbacks = [callback for callback in callbacks if callback is not None]
    if not active_callbacks:
        return None

    def _composed(event: WorkflowProgressEvent) -> None:
        for callback in active_callbacks:
            callback(event)

    return _composed


class LiveRunTracer:
    def __init__(
        self,
        *,
        report_dir: Path,
        case_id: str,
        smiles: str,
        user_query: str,
    ) -> None:
        self._report_dir = report_dir
        self._case_id = case_id
        self._smiles = smiles
        self._user_query = user_query
        self._events: list[dict[str, object]] = []
        self._live_trace_path = report_dir / "live_trace.jsonl"
        self._live_status_path = report_dir / "live_status.md"
        self._write_status_file()

    def handle_event(self, event: WorkflowProgressEvent) -> None:
        serializable_event = {
            "phase": event["phase"],
            "round": event["round"],
            "node": event["node"],
            "agent": event["agent"],
            "case_id": event.get("case_id"),
            "current_hypothesis": event.get("current_hypothesis"),
            "details": event.get("details", {}),
        }
        self._events.append(serializable_event)
        self._live_trace_path.write_text(
            "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in self._events),
            encoding="utf-8",
        )
        self._write_status_file()

    def _write_status_file(self) -> None:
        lines = [
            "# Live Run Status",
            "",
            f"- case_id: {self._case_id}",
            f"- smiles: {self._smiles}",
            f"- report_dir: {self._report_dir}",
            f"- events_recorded: {len(self._events)}",
            "",
            "## Current Position",
        ]
        current_event = self._events[-1] if self._events else None
        if current_event is None:
            lines.append("- status: initialized")
        else:
            lines.extend(
                [
                    f"- phase: {current_event['phase']}",
                    f"- round: {current_event['round']}",
                    f"- agent: {current_event['agent']}",
                    f"- node: {current_event['node']}",
                    f"- current_hypothesis: {current_event.get('current_hypothesis')}",
                ]
            )
        probe_events = [event for event in self._events if event["phase"] == "probe"]
        lines.extend(["", "## Probe Trace"])
        if not probe_events:
            lines.append("")
            lines.append("No microscopic probe events have been recorded yet.")
        else:
            for event in probe_events[-20:]:
                round_label = "setup" if event["round"] == 0 else str(event["round"])
                details = event.get("details") or {}
                stage = details.get("probe_stage", "unknown")
                status = details.get("probe_status", "unknown")
                lines.extend(
                    [
                        "",
                        f"- round={round_label} stage={stage} status={status}",
                    ]
                )
                for key, value in details.items():
                    if key in {"probe_stage", "probe_status"}:
                        continue
                    rendered_value = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
                    lines.append(f"  {key}: {rendered_value}")
        lines.extend(["", "## Round Trace"])

        end_events = [event for event in self._events if event["phase"] == "end"]
        if not end_events:
            lines.append("")
            lines.append("No completed node output has been recorded yet.")
        else:
            for event in end_events:
                round_label = "setup" if event["round"] == 0 else str(event["round"])
                lines.extend(
                    [
                        "",
                        f"### Round {round_label} | {event['agent']} | {event['node']}",
                    ]
                )
                details = event.get("details") or {}
                if not details:
                    lines.append("")
                    lines.append("No structured details were recorded for this node.")
                    continue
                for key, value in details.items():
                    rendered_value = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
                    lines.extend(["", f"- {key}: {rendered_value}"])

        self._live_status_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def cli() -> None:
    app()


if __name__ == "__main__":
    cli()
