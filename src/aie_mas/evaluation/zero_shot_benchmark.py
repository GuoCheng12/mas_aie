from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field

from aie_mas.config import AieMasConfig
from aie_mas.graph.state import HypothesisEntry
from aie_mas.llm.openai_compatible import OpenAICompatiblePlannerClient
from aie_mas.utils.prompts import PromptRepository

ALLOWED_ZERO_SHOT_LABELS = ("ICT", "TICT", "ESIPT", "neutral aromatic", "unknown")
_LABEL_MAP = {
    "ict": "ICT",
    "tict": "TICT",
    "esipt": "ESIPT",
    "neutral aromatic": "neutral aromatic",
    "neutral-aromatic": "neutral aromatic",
    "neutral_aromatic": "neutral aromatic",
    "unknown": "unknown",
    "uncertain": "unknown",
    "undetermined": "unknown",
}
ZERO_SHOT_RESULT_COLUMNS = (
    "id",
    "code",
    "SMILES",
    "mechanism_id",
    "predicted_top1",
    "predicted_confidence",
    "predicted_top2",
    "predicted_top2_confidence",
    "is_correct",
    "workflow_status",
    "error_message",
    "reasoning_summary",
    "hypothesis_pool_json",
)


class ZeroShotMechanismResponse(BaseModel):
    hypothesis_pool: list[HypothesisEntry] = Field(default_factory=list)
    current_hypothesis: str
    confidence: float
    reasoning_summary: str
    hypothesis_reweight_explanation: dict[str, str] = Field(default_factory=dict)


class ZeroShotPredictor:
    def __init__(
        self,
        *,
        config: AieMasConfig,
        prompt_repo: PromptRepository | None = None,
        client: OpenAICompatiblePlannerClient | None = None,
    ) -> None:
        self._config = config
        self._prompt_repo = prompt_repo or PromptRepository(config.prompts_dir)
        self._client = client or OpenAICompatiblePlannerClient(config)

    def predict(self, smiles: str) -> dict[str, Any]:
        system_prompt = self._prompt_repo.read_text("zero_shot_mechanism")
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"SMILES:\n{smiles}"},
        ]
        response = self._client.invoke_json_schema(
            messages=messages,
            response_model=ZeroShotMechanismResponse,
            schema_name="zero_shot_mechanism_response",
        )
        hypothesis_pool, current_hypothesis = _normalize_zero_shot_pool(
            response.hypothesis_pool,
            response.current_hypothesis,
            fallback_confidence=response.confidence,
        )
        predicted_top2, predicted_top2_confidence = _runner_up_from_pool(hypothesis_pool, current_hypothesis)
        return {
            "predicted_top1": current_hypothesis,
            "predicted_confidence": _confidence_for_label(hypothesis_pool, current_hypothesis),
            "predicted_top2": predicted_top2,
            "predicted_top2_confidence": predicted_top2_confidence,
            "reasoning_summary": response.reasoning_summary.strip(),
            "hypothesis_pool_json": json.dumps(
                [entry.model_dump(mode="json") for entry in hypothesis_pool],
                ensure_ascii=False,
            ),
            "hypothesis_reweight_explanation": _normalize_reweight_explanation(
                response.hypothesis_reweight_explanation,
                hypothesis_pool=hypothesis_pool,
            ),
        }


def evaluate_zero_shot_rows(
    rows: list[dict[str, str]],
    *,
    predictor: ZeroShotPredictor,
    progress_callback: Optional[Callable[[int, int, dict[str, str]], None]] = None,
    result_callback: Optional[Callable[[int, int, dict[str, Any]], None]] = None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    total = len(rows)
    for index, row in enumerate(rows, start=1):
        if progress_callback is not None:
            progress_callback(index, total, row)
        try:
            prediction = predictor.predict(row["SMILES"])
        except Exception as exc:  # pragma: no cover
            result_row = {
                **row,
                "predicted_top1": "",
                "predicted_confidence": None,
                "predicted_top2": "",
                "predicted_top2_confidence": None,
                "is_correct": False,
                "workflow_status": "failed",
                "error_message": f"{type(exc).__name__}: {exc}",
                "reasoning_summary": "",
                "hypothesis_pool_json": "",
            }
            results.append(result_row)
            if result_callback is not None:
                result_callback(index, total, result_row)
            continue

        result_row = {
            **row,
            **prediction,
            "is_correct": prediction["predicted_top1"] == row["mechanism_id"],
            "workflow_status": "success",
            "error_message": "",
        }
        results.append(result_row)
        if result_callback is not None:
            result_callback(index, total, result_row)
    return results


def summarize_zero_shot_results(
    *,
    dataset_rows: list[dict[str, str]],
    sampled_rows: list[dict[str, str]],
    evaluated_results: list[dict[str, Any]],
    seed: int,
    model: str,
) -> dict[str, Any]:
    total_evaluated = len(evaluated_results)
    correct = sum(1 for row in evaluated_results if row["is_correct"])
    accuracy = round(correct / total_evaluated, 6) if total_evaluated else None
    per_label: list[dict[str, Any]] = []
    recall_values: list[float] = []
    for label in ALLOWED_ZERO_SHOT_LABELS:
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
        "mode": "zero_shot",
        "model": model,
        "supported_mechanism_labels": list(ALLOWED_ZERO_SHOT_LABELS),
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


def write_zero_shot_outputs(
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
    summary_path = output_dir / "summary.md"

    _write_csv(sampled_dataset_path, ("id", "code", "SMILES", "mechanism_id"), sampled_rows)
    _write_csv(case_results_path, ZERO_SHOT_RESULT_COLUMNS, evaluated_results)
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary_path.write_text(
        _render_zero_shot_summary(metrics=metrics, evaluated_results=evaluated_results),
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


def _render_zero_shot_summary(
    *,
    metrics: dict[str, Any],
    evaluated_results: list[dict[str, Any]],
) -> str:
    lines = [
        "# Zero-Shot Benchmark Summary",
        "",
        f"- mode: {metrics['mode']}",
        f"- model: {metrics['model']}",
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
    for row in metrics["per_label"]:
        lines.append(
            f"| {row['label']} | {row['support']} | {row['predicted_count']} | "
            f"{row['true_positive']} | {row['recall']} | {row['precision']} |"
        )
    lines.extend(
        [
            "",
            "## Case Results",
            "",
            "| id | code | truth | predicted_top1 | confidence | status | is_correct |",
            "| --- | --- | --- | --- | ---: | --- | --- |",
        ]
    )
    for row in evaluated_results:
        lines.append(
            f"| {row['id']} | {row['code']} | {row['mechanism_id']} | "
            f"{row['predicted_top1'] or '-'} | {row['predicted_confidence']} | "
            f"{row['workflow_status']} | {row['is_correct']} |"
        )
    return "\n".join(lines) + "\n"


def _normalize_zero_shot_pool(
    raw_pool: list[HypothesisEntry],
    raw_current_hypothesis: str,
    *,
    fallback_confidence: float | None = None,
) -> tuple[list[HypothesisEntry], str]:
    normalized_entries: dict[str, HypothesisEntry] = {}
    for entry in raw_pool:
        label = _normalize_label(entry.name)
        if label is None:
            continue
        normalized_entries[label] = HypothesisEntry(
            name=label,
            confidence=max(0.0, float(entry.confidence)),
            rationale=entry.rationale,
            candidate_strength=entry.candidate_strength,
        )
    current_hypothesis = _normalize_label(raw_current_hypothesis) or "unknown"
    for label in ALLOWED_ZERO_SHOT_LABELS:
        normalized_entries.setdefault(
            label,
            HypothesisEntry(name=label, confidence=0.0, rationale=None, candidate_strength="weak"),
        )
    total = sum(max(0.0, float(entry.confidence or 0.0)) for entry in normalized_entries.values())
    if total <= 0.0:
        top_confidence = max(0.0, float(fallback_confidence or 0.0))
        normalized_entries[current_hypothesis].confidence = top_confidence
        normalized_entries["unknown"].confidence = max(0.0, 1.0 - top_confidence) if current_hypothesis != "unknown" else 1.0
        for label in ALLOWED_ZERO_SHOT_LABELS:
            if label not in {current_hypothesis, "unknown"}:
                normalized_entries[label].confidence = 0.0
    else:
        for entry in normalized_entries.values():
            entry.confidence = round(max(0.0, float(entry.confidence or 0.0)) / total, 6)
    normalized_pool = sorted(
        normalized_entries.values(),
        key=lambda entry: (-float(entry.confidence or 0.0), ALLOWED_ZERO_SHOT_LABELS.index(entry.name)),
    )
    return normalized_pool, normalized_pool[0].name


def _normalize_reweight_explanation(
    raw_explanation: dict[str, str],
    *,
    hypothesis_pool: list[HypothesisEntry],
) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for raw_label, text in raw_explanation.items():
        label = _normalize_label(raw_label)
        if label is None:
            continue
        normalized[label] = text.strip()
    for entry in hypothesis_pool:
        normalized.setdefault(entry.name, f"Assigned confidence {float(entry.confidence or 0.0):.3f} from the SMILES-only zero-shot read.")
    return normalized


def _runner_up_from_pool(hypothesis_pool: list[HypothesisEntry], current_hypothesis: str) -> tuple[str | None, float | None]:
    for entry in hypothesis_pool:
        if entry.name != current_hypothesis:
            return entry.name, float(entry.confidence or 0.0)
    return None, None


def _confidence_for_label(hypothesis_pool: list[HypothesisEntry], label: str) -> float:
    for entry in hypothesis_pool:
        if entry.name == label:
            return float(entry.confidence or 0.0)
    return 0.0


def _normalize_label(raw_label: str | None) -> str | None:
    if raw_label is None:
        return None
    collapsed = re.sub(r"[\s_-]+", " ", raw_label.strip().lower())
    return _LABEL_MAP.get(collapsed)
