from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, Optional

import typer
import yaml

from aie_mas.cli.run_case import run_case_workflow, run_case_workflow_with_reporting
from aie_mas.evaluation.dataset_benchmark import (
    DEFAULT_USER_QUERY,
    default_output_dir,
    evaluate_benchmark_rows,
    load_benchmark_rows,
    select_benchmark_sample,
    summarize_benchmark_results,
    write_benchmark_outputs,
)

app = typer.Typer(add_completion=False)

BENCHMARK_CONFIG_KEYS = {
    "dataset_path",
    "n",
    "seed",
    "output_dir",
    "user_query",
    "execution_profile",
    "show_case_progress",
}
PATH_CONFIG_KEYS = {
    "dataset_path",
    "output_dir",
    "prompts_dir",
    "data_dir",
    "memory_dir",
    "report_dir",
    "log_dir",
    "runtime_dir",
    "tools_work_dir",
    "atb_binary_path",
    "amesp_binary_path",
    "external_search_binary_path",
}
RUN_CASE_RUNTIME_KEYS = {
    name
    for name in inspect.signature(run_case_workflow).parameters
    if name not in {"smiles", "user_query", "progress_callback"}
}


def _coerce_bool(value: Any, *, key: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    raise typer.BadParameter(f"Config field {key!r} must be a boolean, got {value!r}.")


def _load_config_file(config_file: Optional[Path]) -> tuple[dict[str, Any], Optional[Path]]:
    if config_file is None:
        return {}, None
    resolved_path = config_file.expanduser().resolve()
    if not resolved_path.exists():
        raise typer.BadParameter(f"Config file does not exist: {resolved_path}")
    payload = yaml.safe_load(resolved_path.read_text(encoding="utf-8"))
    if payload is None:
        return {}, resolved_path
    if not isinstance(payload, dict):
        raise typer.BadParameter("Config file must contain a top-level mapping.")

    normalized: dict[str, Any] = {}
    for raw_key, value in payload.items():
        if not isinstance(raw_key, str):
            raise typer.BadParameter("Config file keys must be strings.")
        key = raw_key.strip().lstrip("-").replace("-", "_")
        normalized[key] = value

    if "disable_long_term_memory" in normalized:
        if "enable_long_term_memory" in normalized:
            raise typer.BadParameter(
                "Config file cannot specify both disable_long_term_memory and "
                "enable_long_term_memory."
            )
        normalized["enable_long_term_memory"] = not _coerce_bool(
            normalized.pop("disable_long_term_memory"),
            key="disable_long_term_memory",
        )
    if "hide_case_progress" in normalized:
        if "show_case_progress" in normalized:
            raise typer.BadParameter(
                "Config file cannot specify both hide_case_progress and "
                "show_case_progress."
            )
        normalized["show_case_progress"] = not _coerce_bool(
            normalized.pop("hide_case_progress"),
            key="hide_case_progress",
        )

    for bool_key in {"enable_long_term_memory", "show_case_progress", "amesp_use_ricosx"}:
        if bool_key in normalized:
            normalized[bool_key] = _coerce_bool(normalized[bool_key], key=bool_key)

    for path_key in PATH_CONFIG_KEYS:
        value = normalized.get(path_key)
        if value is None:
            continue
        if not isinstance(value, (str, Path)):
            raise typer.BadParameter(f"Config field {path_key!r} must be a path string.")
        path_value = Path(value).expanduser()
        if not path_value.is_absolute():
            path_value = (resolved_path.parent / path_value).resolve()
        normalized[path_key] = path_value

    unknown_keys = sorted(set(normalized) - BENCHMARK_CONFIG_KEYS - RUN_CASE_RUNTIME_KEYS)
    if unknown_keys:
        raise typer.BadParameter(
            "Config file contains unsupported keys: " + ", ".join(unknown_keys)
        )
    return normalized, resolved_path


def _resolve_runtime_kwargs(config_values: dict[str, Any]) -> dict[str, Any]:
    runtime_kwargs = {
        key: value
        for key, value in config_values.items()
        if key in RUN_CASE_RUNTIME_KEYS and value is not None
    }
    runtime_kwargs.setdefault("enable_long_term_memory", False)
    return runtime_kwargs


@app.command()
def main(
    config_file: Optional[Path] = typer.Option(
        None,
        "--config-file",
        help="YAML config file for benchmark sampling and workflow runtime options.",
    ),
    dataset_path: Optional[Path] = typer.Option(
        None,
        "--dataset-path",
        help="CSV dataset containing SMILES and mechanism_id.",
    ),
    n: Optional[int] = typer.Option(
        None,
        "--n",
        min=1,
        help="Randomly sample and evaluate n molecules. Omit to evaluate all dataset rows.",
    ),
    seed: Optional[int] = typer.Option(
        None,
        "--seed",
        help="Random seed used when --n is provided.",
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        help="Directory where per-case results and metrics will be written.",
    ),
    user_query: Optional[str] = typer.Option(
        None,
        "--user-query",
        help="User query passed to each workflow run.",
    ),
    execution_profile: Optional[str] = typer.Option(
        None,
        "--execution-profile",
        help="Optional execution profile override. Otherwise use environment/default config.",
    ),
    show_case_progress: Optional[bool] = typer.Option(
        None,
        "--show-case-progress/--hide-case-progress",
        help="Print one benchmark progress line per evaluated molecule.",
    ),
) -> None:
    config_values, resolved_config_file = _load_config_file(config_file)
    merged_values = dict(config_values)
    cli_overrides = {
        "dataset_path": dataset_path,
        "n": n,
        "seed": seed,
        "output_dir": output_dir,
        "user_query": user_query,
        "execution_profile": execution_profile,
        "show_case_progress": show_case_progress,
    }
    for key, value in cli_overrides.items():
        if value is not None:
            merged_values[key] = value

    dataset_value = merged_values.get("dataset_path", Path("dataset/1_level.csv"))
    dataset_path = Path(dataset_value).expanduser().resolve()
    if not dataset_path.exists():
        raise typer.BadParameter(f"Dataset file does not exist: {dataset_path}")

    sample_size = merged_values.get("n")
    if sample_size is not None:
        try:
            sample_size = int(sample_size)
        except (TypeError, ValueError) as exc:
            raise typer.BadParameter("--n must be a positive integer.") from exc
        if sample_size < 1:
            raise typer.BadParameter("--n must be a positive integer.")

    seed_value = merged_values.get("seed", 0)
    try:
        seed = int(seed_value)
    except (TypeError, ValueError) as exc:
        raise typer.BadParameter("--seed must be an integer.") from exc

    user_query = str(merged_values.get("user_query", DEFAULT_USER_QUERY))
    if "show_case_progress" in merged_values:
        show_case_progress = _coerce_bool(
            merged_values["show_case_progress"],
            key="show_case_progress",
        )
    else:
        show_case_progress = True

    rows = load_benchmark_rows(dataset_path)
    sampled_rows = select_benchmark_sample(rows, sample_size=sample_size, seed=seed)
    runtime_kwargs = _resolve_runtime_kwargs(merged_values)

    def _progress(index: int, total: int, row: dict[str, str]) -> None:
        if not show_case_progress:
            return
        typer.echo(
            f"[{index}/{total}] start code={row.get('code') or '-'} truth={row['mechanism_id']} "
            f"smiles_length={len(row['SMILES'])}"
        )

    def _result(index: int, total: int, result: dict[str, Any]) -> None:
        if not show_case_progress:
            return
        if result["workflow_status"] == "success":
            typer.echo(
                f"[{index}/{total}] done code={result.get('code') or '-'} "
                f"truth={result['mechanism_id']} top1={result['predicted_top1'] or '-'} "
                f"correct={result['is_correct']} rounds={result['working_memory_rounds']} "
                f"report_dir={result['report_dir'] or '-'}"
            )
            return
        typer.echo(
            f"[{index}/{total}] failed code={result.get('code') or '-'} "
            f"truth={result['mechanism_id']} error={result['error_message']} "
            f"report_dir={result['report_dir'] or '-'}"
        )

    def _workflow_runner(*, smiles: str, user_query: str, **kwargs: Any) -> Any:
        return run_case_workflow_with_reporting(
            smiles=smiles,
            user_query=user_query,
            show_progress=show_case_progress,
            **kwargs,
        )

    evaluated_results = evaluate_benchmark_rows(
        sampled_rows,
        workflow_runner=_workflow_runner,
        user_query=user_query,
        runtime_kwargs=runtime_kwargs,
        progress_callback=_progress,
        result_callback=_result,
    )
    metrics = summarize_benchmark_results(
        dataset_rows=rows,
        sampled_rows=sampled_rows,
        evaluated_results=evaluated_results,
        seed=seed,
    )
    output_value = merged_values.get("output_dir")
    if output_value is None:
        output_dir = default_output_dir(Path.cwd())
    else:
        output_dir = Path(output_value).expanduser().resolve()
    output_paths = write_benchmark_outputs(
        output_dir,
        sampled_rows=sampled_rows,
        evaluated_results=evaluated_results,
        metrics=metrics,
    )

    if resolved_config_file is not None:
        typer.echo(f"config_file: {resolved_config_file}")
    typer.echo(f"dataset_path: {dataset_path}")
    typer.echo(f"dataset_rows: {metrics['dataset_row_count']}")
    typer.echo(f"sampled_rows: {metrics['sampled_row_count']}")
    typer.echo(f"evaluated_rows: {metrics['evaluated_row_count']}")
    typer.echo(f"top1_accuracy: {metrics['top1_accuracy']}")
    typer.echo(f"macro_recall: {metrics['macro_recall']}")
    typer.echo(f"output_dir: {output_paths['output_dir']}")
    typer.echo(f"sampled_dataset: {output_paths['sampled_dataset_path']}")
    typer.echo(f"case_results: {output_paths['case_results_path']}")
    typer.echo(f"metrics_json: {output_paths['metrics_path']}")
    typer.echo(f"summary_md: {output_paths['summary_path']}")


def cli() -> None:
    app()


if __name__ == "__main__":
    cli()
