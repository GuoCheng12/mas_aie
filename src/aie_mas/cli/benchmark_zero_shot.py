from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import typer

from aie_mas.config import AieMasConfig
from aie_mas.evaluation.dataset_benchmark import (
    load_benchmark_rows,
    select_benchmark_sample,
)
from aie_mas.evaluation.zero_shot_benchmark import (
    ZeroShotPredictor,
    evaluate_zero_shot_rows,
    summarize_zero_shot_results,
    write_zero_shot_outputs,
)

app = typer.Typer(add_completion=False)


@app.command()
def main(
    dataset_path: Path = typer.Option(
        Path("dataset/1_level.csv"),
        "--dataset-path",
        help="CSV dataset containing SMILES and mechanism_id.",
    ),
    n: Optional[int] = typer.Option(
        None,
        "--n",
        min=1,
        help="Randomly sample and evaluate n molecules. Omit to evaluate all dataset rows.",
    ),
    seed: int = typer.Option(
        0,
        "--seed",
        help="Random seed used when --n is provided.",
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        help="Directory where zero-shot benchmark outputs will be written.",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        help="LLM model used for zero-shot prediction. Defaults to the current planner model config.",
    ),
    base_url: Optional[str] = typer.Option(
        None,
        "--base-url",
        help="OpenAI-compatible base URL. Defaults to the current planner base_url config.",
    ),
    api_key: Optional[str] = typer.Option(
        None,
        "--api-key",
        help="API key for the zero-shot LLM. Defaults to the current planner API key config.",
    ),
    temperature: Optional[float] = typer.Option(
        None,
        "--temperature",
        help="Sampling temperature. Defaults to the current planner temperature config.",
    ),
    timeout_seconds: Optional[float] = typer.Option(
        None,
        "--timeout-seconds",
        help="Request timeout in seconds. Defaults to the current planner timeout config.",
    ),
    show_progress: bool = typer.Option(
        True,
        "--show-progress/--hide-progress",
        help="Print one progress line per evaluated molecule.",
    ),
) -> None:
    dataset_path = dataset_path.expanduser().resolve()
    if not dataset_path.exists():
        raise typer.BadParameter(f"Dataset file does not exist: {dataset_path}")

    config = AieMasConfig.from_env(
        planner_model=model,
        planner_base_url=base_url,
        planner_api_key=api_key,
        planner_temperature=temperature,
        planner_timeout_seconds=timeout_seconds,
    )
    rows = load_benchmark_rows(dataset_path)
    sampled_rows = select_benchmark_sample(rows, sample_size=n, seed=seed)

    if output_dir is None:
        output_dir = (Path.cwd() / "benchmark_runs" / "zero_shot").resolve()
    else:
        output_dir = output_dir.expanduser().resolve()

    predictor = ZeroShotPredictor(config=config)
    partial_results: list[dict[str, Any]] = []
    output_paths = write_zero_shot_outputs(
        output_dir,
        sampled_rows=sampled_rows,
        evaluated_results=[],
        metrics=summarize_zero_shot_results(
            dataset_rows=rows,
            sampled_rows=sampled_rows,
            evaluated_results=[],
            seed=seed,
            model=config.planner_model,
        ),
    )

    def _progress(index: int, total: int, row: dict[str, str]) -> None:
        if not show_progress:
            return
        typer.echo(
            f"[{index}/{total}] start code={row.get('code') or '-'} truth={row['mechanism_id']} "
            f"smiles_length={len(row['SMILES'])}"
        )

    def _result(index: int, total: int, result: dict[str, Any]) -> None:
        nonlocal output_paths
        partial_results.append(dict(result))
        partial_metrics = summarize_zero_shot_results(
            dataset_rows=rows,
            sampled_rows=sampled_rows,
            evaluated_results=partial_results,
            seed=seed,
            model=config.planner_model,
        )
        output_paths = write_zero_shot_outputs(
            output_dir,
            sampled_rows=sampled_rows,
            evaluated_results=partial_results,
            metrics=partial_metrics,
        )
        if not show_progress:
            return
        if result["workflow_status"] == "success":
            typer.echo(
                f"[{index}/{total}] done code={result.get('code') or '-'} "
                f"truth={result['mechanism_id']} top1={result['predicted_top1'] or '-'} "
                f"correct={result['is_correct']} running_accuracy={partial_metrics['top1_accuracy']}"
            )
            return
        typer.echo(
            f"[{index}/{total}] failed code={result.get('code') or '-'} "
            f"truth={result['mechanism_id']} error={result['error_message']} "
            f"running_accuracy={partial_metrics['top1_accuracy']}"
        )

    evaluated_results = evaluate_zero_shot_rows(
        sampled_rows,
        predictor=predictor,
        progress_callback=_progress,
        result_callback=_result,
    )
    metrics = summarize_zero_shot_results(
        dataset_rows=rows,
        sampled_rows=sampled_rows,
        evaluated_results=evaluated_results,
        seed=seed,
        model=config.planner_model,
    )
    output_paths = write_zero_shot_outputs(
        output_dir,
        sampled_rows=sampled_rows,
        evaluated_results=evaluated_results,
        metrics=metrics,
    )

    typer.echo(f"dataset_path: {dataset_path}")
    typer.echo(f"model: {config.planner_model}")
    typer.echo(f"base_url: {config.planner_base_url}")
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
