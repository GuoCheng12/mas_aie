from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aie_mas.cli import benchmark_dataset as benchmark_cli
from aie_mas.evaluation.dataset_benchmark import (
    BENCHMARK_TABLE_COLUMNS,
    evaluate_benchmark_rows,
    load_benchmark_rows,
    select_benchmark_sample,
    summarize_benchmark_results,
    write_benchmark_outputs,
)
from aie_mas.graph.state import AieMasState


def test_load_benchmark_rows_requires_sanitized_dataset_schema(tmp_path: Path) -> None:
    dataset_path = tmp_path / "dataset.csv"
    dataset_path.write_text(
        "id,code,SMILES,mechanism_id\n"
        "1,a,C,ICT\n"
        "2,b,CC,neutral aromatic\n",
        encoding="utf-8",
    )

    rows = load_benchmark_rows(dataset_path)

    assert rows == [
        {"id": "1", "code": "a", "SMILES": "C", "mechanism_id": "ICT"},
        {"id": "2", "code": "b", "SMILES": "CC", "mechanism_id": "neutral aromatic"},
    ]


def test_load_benchmark_rows_rejects_unsanitized_dataset(tmp_path: Path) -> None:
    dataset_path = tmp_path / "dataset.csv"
    dataset_path.write_text(
        "id,code,SMILES,mechanism_id,extra\n"
        "1,a,C,ICT,foo\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Expected dataset columns"):
        load_benchmark_rows(dataset_path)


def test_select_benchmark_sample_is_seeded() -> None:
    rows = [
        {"id": "1", "code": "a", "SMILES": "C", "mechanism_id": "ICT"},
        {"id": "2", "code": "b", "SMILES": "CC", "mechanism_id": "TICT"},
        {"id": "3", "code": "c", "SMILES": "CCC", "mechanism_id": "ESIPT"},
    ]

    sample = select_benchmark_sample(rows, sample_size=2, seed=7)

    assert sample == [
        {"id": "2", "code": "b", "SMILES": "CC", "mechanism_id": "TICT"},
        {"id": "1", "code": "a", "SMILES": "C", "mechanism_id": "ICT"},
    ]


def test_evaluate_and_summarize_benchmark_rows(tmp_path: Path) -> None:
    rows = [
        {"id": "1", "code": "a", "SMILES": "C", "mechanism_id": "ICT"},
        {"id": "2", "code": "b", "SMILES": "CC", "mechanism_id": "TICT"},
    ]

    def _fake_runner(*, smiles: str, user_query: str, **kwargs) -> AieMasState:
        del user_query, kwargs
        predicted = "ICT" if smiles == "C" else "neutral aromatic"
        return AieMasState(
            user_query="benchmark",
            smiles=smiles,
            current_hypothesis=predicted,
            confidence=0.8,
            finalize=True,
        )

    evaluated = evaluate_benchmark_rows(rows, workflow_runner=_fake_runner)
    metrics = summarize_benchmark_results(
        dataset_rows=rows,
        sampled_rows=rows,
        evaluated_results=evaluated,
        seed=11,
    )
    output_paths = write_benchmark_outputs(
        tmp_path,
        sampled_rows=rows,
        evaluated_results=evaluated,
        metrics=metrics,
    )

    assert evaluated[0]["predicted_top1"] == "ICT"
    assert evaluated[0]["is_correct"] is True
    assert evaluated[1]["predicted_top1"] == "neutral aromatic"
    assert evaluated[1]["is_correct"] is False
    assert metrics["top1_accuracy"] == 0.5
    assert metrics["dataset_row_count"] == 2
    per_label = {entry["label"]: entry for entry in metrics["per_label"]}
    assert per_label["ICT"]["recall"] == 1.0
    assert per_label["TICT"]["recall"] == 0.0

    case_results_path = output_paths["case_results_path"]
    sampled_dataset_path = output_paths["sampled_dataset_path"]
    metrics_path = output_paths["metrics_path"]
    assert case_results_path.exists()
    assert sampled_dataset_path.exists()
    assert metrics_path.exists()

    with sampled_dataset_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert tuple(reader.fieldnames or ()) == BENCHMARK_TABLE_COLUMNS
        rows_out = list(reader)
        assert rows_out[0]["SMILES"] == "C"

    with case_results_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert tuple(reader.fieldnames or ()) == (
            *BENCHMARK_TABLE_COLUMNS,
            "predicted_top1",
            "predicted_confidence",
            "is_correct",
            "workflow_status",
            "error_message",
            "case_id",
            "working_memory_rounds",
            "finalize",
        )
        rows_out = list(reader)
        assert rows_out[0]["predicted_top1"] == "ICT"

    metrics_payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metrics_payload["top1_accuracy"] == 0.5


def test_benchmark_cli_reads_config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dataset_path = tmp_path / "dataset.csv"
    dataset_path.write_text(
        "id,code,SMILES,mechanism_id\n"
        "1,a,C,ICT\n",
        encoding="utf-8",
    )
    config_path = tmp_path / "benchmark.yaml"
    config_path.write_text(
        "dataset_path: dataset.csv\n"
        "n: 1\n"
        "seed: 9\n"
        "output_dir: outputs\n"
        "execution_profile: linux-prod\n"
        "tool_backend: real\n"
        "disable_long_term_memory: true\n"
        "amesp_npara: 22\n"
        "amesp_maxcore_mb: 16000\n"
        "show_case_progress: false\n",
        encoding="utf-8",
    )

    captured_kwargs: list[dict[str, object]] = []

    def _fake_runner(*, smiles: str, user_query: str, **kwargs) -> AieMasState:
        del user_query
        captured_kwargs.append({"smiles": smiles, **kwargs})
        return AieMasState(
            user_query="benchmark",
            smiles=smiles,
            current_hypothesis="ICT",
            confidence=0.9,
            finalize=True,
        )

    monkeypatch.setattr(benchmark_cli, "run_case_workflow", _fake_runner)
    runner = CliRunner()
    result = runner.invoke(benchmark_cli.app, ["--config-file", str(config_path)])

    assert result.exit_code == 0, result.output
    assert "top1_accuracy:" in result.output
    assert len(captured_kwargs) == 1
    assert captured_kwargs[0]["smiles"] == "C"
    assert captured_kwargs[0]["execution_profile"] == "linux-prod"
    assert captured_kwargs[0]["tool_backend"] == "real"
    assert captured_kwargs[0]["enable_long_term_memory"] is False
    assert captured_kwargs[0]["amesp_npara"] == 22
    assert captured_kwargs[0]["amesp_maxcore_mb"] == 16000
    assert (tmp_path / "outputs" / "metrics.json").exists()
