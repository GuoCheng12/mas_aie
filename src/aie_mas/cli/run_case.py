from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from aie_mas.config import AieMasConfig, ExecutionProfile, ToolBackend
from aie_mas.graph.builder import build_graph, invoke_graph
from aie_mas.graph.state import AieMasState

app = typer.Typer(add_completion=False)


def build_runtime_config(
    execution_profile: Optional[ExecutionProfile] = None,
    tool_backend: Optional[ToolBackend] = None,
    prompts_dir: Optional[Path] = None,
    data_dir: Optional[Path] = None,
    memory_dir: Optional[Path] = None,
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
        prompts_dir=prompts_dir,
        data_dir=data_dir,
        memory_dir=memory_dir,
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
    prompts_dir: Optional[Path] = None,
    data_dir: Optional[Path] = None,
    memory_dir: Optional[Path] = None,
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
        prompts_dir=prompts_dir,
        data_dir=data_dir,
        memory_dir=memory_dir,
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
    execution_profile: str = typer.Option(
        "local-dev",
        help="Execution profile: local-dev for local mock validation, linux-prod for Linux deployment.",
    ),
    tool_backend: str = typer.Option(
        "mock",
        help="Tool backend: mock for current first-stage runs, real for future Linux wrappers.",
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
        prompts_dir=prompts_dir,
        data_dir=data_dir,
        memory_dir=memory_dir,
        log_dir=log_dir,
        runtime_dir=runtime_dir,
        tools_work_dir=tools_work_dir,
        atb_binary_path=atb_binary_path,
        amesp_binary_path=amesp_binary_path,
        external_search_binary_path=external_search_binary_path,
    )
    graph = build_graph(config)
    state = invoke_graph(graph, AieMasState(user_query=user_query, smiles=smiles))
    payload = {
        "runtime_context": config.runtime_context(),
        "final_answer": state.final_answer,
        "state_snapshot": state.state_snapshot,
    }
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


def cli() -> None:
    app()


if __name__ == "__main__":
    cli()
