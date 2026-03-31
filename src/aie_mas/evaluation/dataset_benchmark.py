from __future__ import annotations

import csv
import json
import random
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from aie_mas.agents.planner import ALLOWED_HYPOTHESIS_LABELS
from aie_mas.cli.run_case import WorkflowRunArtifacts, run_case_workflow
from aie_mas.graph.state import AieMasState

SUPPORTED_MECHANISM_LABELS = tuple(ALLOWED_HYPOTHESIS_LABELS)
BENCHMARK_TABLE_COLUMNS = ("id", "code", "SMILES", "mechanism_id")
DEFAULT_USER_QUERY = "Assess the likely AIE mechanism for this molecule."


def load_benchmark_rows(dataset_path: Path) -> list[dict[str, str]]:
    with dataset_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = tuple(reader.fieldnames or ())
        if fieldnames != BENCHMARK_TABLE_COLUMNS:
            raise ValueError(
                f"Expected dataset columns {BENCHMARK_TABLE_COLUMNS}, but got {fieldnames}."
            )
        rows = [{column: (row.get(column) or "").strip() for column in BENCHMARK_TABLE_COLUMNS} for row in reader]

    for row in rows:
        mechanism_id = row["mechanism_id"]
        smiles = row["SMILES"]
        if mechanism_id not in SUPPORTED_MECHANISM_LABELS:
            raise ValueError(
                f"Dataset contains unsupported mechanism_id={mechanism_id!r}; sanitize the dataset first."
            )
        if not smiles:
            raise ValueError("Dataset contains an empty SMILES entry; sanitize the dataset first.")
    return rows


def select_benchmark_sample(
    rows: list[dict[str, str]],
    *,
    sample_size: Optional[int],
    seed: int,
) -> list[dict[str, str]]:
    if sample_size is None:
        return list(rows)
    if sample_size <= 0:
        raise ValueError("sample_size must be positive when provided.")
    if sample_size > len(rows):
        raise ValueError(f"Requested sample_size={sample_size}, but dataset only contains {len(rows)} rows.")
    rng = random.Random(seed)
    return rng.sample(rows, sample_size)


def evaluate_benchmark_rows(
    rows: list[dict[str, str]],
    *,
    workflow_runner: Callable[..., AieMasState | WorkflowRunArtifacts] = run_case_workflow,
    user_query: str = DEFAULT_USER_QUERY,
    runtime_kwargs: Optional[dict[str, Any]] = None,
    progress_callback: Optional[Callable[[int, int, dict[str, str]], None]] = None,
    result_callback: Optional[Callable[[int, int, dict[str, Any]], None]] = None,
) -> list[dict[str, Any]]:
    runtime_kwargs = dict(runtime_kwargs or {})
    results: list[dict[str, Any]] = []
    total = len(rows)
    for index, row in enumerate(rows, start=1):
        if progress_callback is not None:
            progress_callback(index, total, row)
        try:
            workflow_result = workflow_runner(
                smiles=row["SMILES"],
                user_query=user_query,
                **runtime_kwargs,
            )
        except Exception as exc:  # pragma: no cover
            report_paths = getattr(exc, "report_paths", {}) or {}
            result_row = {
                **row,
                "predicted_top1": "",
                "predicted_confidence": None,
                "is_correct": False,
                "workflow_status": "failed",
                "error_message": f"{type(exc).__name__}: {exc}",
                "case_id": getattr(exc, "case_id", None),
                "working_memory_rounds": None,
                "finalize": False,
                "report_dir": _stringify_path(report_paths.get("report_dir")),
                "summary_path": _stringify_path(report_paths.get("summary_path")),
                "full_state_path": _stringify_path(report_paths.get("full_state_path")),
                "live_trace_path": _stringify_path(report_paths.get("live_trace_path")),
                "live_status_path": _stringify_path(report_paths.get("live_status_path")),
            }
            results.append(result_row)
            if result_callback is not None:
                result_callback(index, total, result_row)
            continue

        state, report_paths = _unpack_workflow_result(workflow_result)
        predicted_top1 = (state.current_hypothesis or "").strip()
        result_row = {
            **row,
            "predicted_top1": predicted_top1,
            "predicted_confidence": state.confidence,
            "is_correct": predicted_top1 == row["mechanism_id"],
            "workflow_status": "success",
            "error_message": "",
            "case_id": state.case_id,
            "working_memory_rounds": len(state.working_memory),
            "finalize": state.finalize,
            "report_dir": _stringify_path(report_paths.get("report_dir")),
            "summary_path": _stringify_path(report_paths.get("summary_path")),
            "full_state_path": _stringify_path(report_paths.get("full_state_path")),
            "live_trace_path": _stringify_path(report_paths.get("live_trace_path")),
            "live_status_path": _stringify_path(report_paths.get("live_status_path")),
        }
        results.append(result_row)
        if result_callback is not None:
            result_callback(index, total, result_row)
    return results


def _unpack_workflow_result(
    workflow_result: AieMasState | WorkflowRunArtifacts,
) -> tuple[AieMasState, dict[str, Path]]:
    if isinstance(workflow_result, WorkflowRunArtifacts):
        return workflow_result.state, workflow_result.report_paths
    return workflow_result, {}


def _stringify_path(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def summarize_benchmark_results(
    *,
    dataset_rows: list[dict[str, str]],
    sampled_rows: list[dict[str, str]],
    evaluated_results: list[dict[str, Any]],
    seed: int,
) -> dict[str, Any]:
    total_evaluated = len(evaluated_results)
    correct = sum(1 for row in evaluated_results if row["is_correct"])
    accuracy = round(correct / total_evaluated, 6) if total_evaluated else None

    per_label: list[dict[str, Any]] = []
    recall_values: list[float] = []
    for label in SUPPORTED_MECHANISM_LABELS:
        actual_rows = [row for row in evaluated_results if row["mechanism_id"] == label]
        predicted_rows = [row for row in evaluated_results if row["predicted_top1"] == label]
        true_positive = sum(1 for row in actual_rows if row["is_correct"])
        recall = round(true_positive / len(actual_rows), 6) if actual_rows else None
        precision = round(true_positive / len(predicted_rows), 6) if predicted_rows else None
        if recall is not None:
            recall_values.append(recall)
        per_label.append(
            {
                "label": label,
                "support": len(actual_rows),
                "predicted_count": len(predicted_rows),
                "true_positive": true_positive,
                "recall": recall,
                "precision": precision,
            }
        )

    return {
        "supported_mechanism_labels": list(SUPPORTED_MECHANISM_LABELS),
        "dataset_row_count": len(dataset_rows),
        "sampled_row_count": len(sampled_rows),
        "evaluated_row_count": total_evaluated,
        "successful_case_count": sum(1 for row in evaluated_results if row["workflow_status"] == "success"),
        "failed_case_count": sum(1 for row in evaluated_results if row["workflow_status"] == "failed"),
        "top1_accuracy": accuracy,
        "macro_recall": round(sum(recall_values) / len(recall_values), 6) if recall_values else None,
        "seed": seed,
        "per_label": per_label,
    }


def default_output_dir(base_dir: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return base_dir / "benchmark_runs" / timestamp


def write_benchmark_outputs(
    output_dir: Path,
    *,
    sampled_rows: list[dict[str, str]],
    evaluated_results: list[dict[str, Any]],
    metrics: dict[str, Any],
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    sampled_dataset_path = output_dir / "sampled_dataset.csv"
    case_results_path = output_dir / "case_results.csv"
    metrics_path = output_dir / "metrics.json"

    _write_csv(sampled_dataset_path, BENCHMARK_TABLE_COLUMNS, sampled_rows)
    _write_csv(
        case_results_path,
        (
            *BENCHMARK_TABLE_COLUMNS,
            "predicted_top1",
            "predicted_confidence",
            "is_correct",
            "workflow_status",
            "error_message",
            "case_id",
            "working_memory_rounds",
            "finalize",
            "report_dir",
            "summary_path",
            "full_state_path",
            "live_trace_path",
            "live_status_path",
        ),
        evaluated_results,
    )
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary_path = output_dir / "summary.md"
    summary_path.write_text(
        _render_benchmark_summary(metrics=metrics, evaluated_results=evaluated_results),
        encoding="utf-8",
    )
    return {
        "output_dir": output_dir,
        "sampled_dataset_path": sampled_dataset_path,
        "case_results_path": case_results_path,
        "metrics_path": metrics_path,
        "summary_path": summary_path,
    }


def _write_csv(path: Path, fieldnames: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _render_benchmark_summary(
    *,
    metrics: dict[str, Any],
    evaluated_results: list[dict[str, Any]],
) -> str:
    lines = [
        "# Benchmark Summary",
        "",
        f"- dataset_row_count: {metrics['dataset_row_count']}",
        f"- sampled_row_count: {metrics['sampled_row_count']}",
        f"- evaluated_row_count: {metrics['evaluated_row_count']}",
        f"- successful_case_count: {metrics['successful_case_count']}",
        f"- failed_case_count: {metrics['failed_case_count']}",
        f"- top1_accuracy: {metrics['top1_accuracy']}",
        f"- macro_recall: {metrics['macro_recall']}",
        "",
        "## Per-label Metrics",
        "",
        "| label | support | predicted_count | true_positive | recall | precision |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for entry in metrics["per_label"]:
        lines.append(
            "| {label} | {support} | {predicted_count} | {true_positive} | {recall} | "
            "{precision} |".format(**entry)
        )
    lines.extend(
        [
            "",
            "## Case Results",
            "",
            "| id | code | truth | predicted_top1 | status | is_correct | report_dir | live_status_path |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in evaluated_results:
        lines.append(
            "| {id} | {code} | {mechanism_id} | {predicted_top1} | {workflow_status} | "
            "{is_correct} | {report_dir} | {live_status_path} |".format(**row)
        )
    lines.append("")
    return "\n".join(lines)
