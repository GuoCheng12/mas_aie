from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from aie_mas.graph.state import (
    AieMasState,
    CaseMemoryEntry,
    ReliabilityMemoryEntry,
    StrategyMemoryEntry,
)
from aie_mas.utils.smiles import scaffold_proxy


class LongTermMemoryStore:
    def __init__(self, memory_dir: Path) -> None:
        self._memory_dir = memory_dir
        self._case_path = self._memory_dir / "case_memory.json"
        self._strategy_path = self._memory_dir / "strategy_memory.json"
        self._reliability_path = self._memory_dir / "reliability_memory.json"
        self._ensure_storage()

    @property
    def memory_dir(self) -> Path:
        return self._memory_dir

    def _ensure_storage(self) -> None:
        self._memory_dir.mkdir(parents=True, exist_ok=True)
        for path in (self._case_path, self._strategy_path, self._reliability_path):
            if not path.exists():
                path.write_text("[]\n", encoding="utf-8")

    def load_case_hits(
        self,
        smiles: str,
        exclude_case_ids: Iterable[str] | None = None,
    ) -> list[CaseMemoryEntry]:
        entries = self._read_entries(self._case_path, CaseMemoryEntry)
        case_scaffold = scaffold_proxy(smiles)
        blocked_case_ids = {case_id for case_id in (exclude_case_ids or []) if case_id}
        filtered = [
            entry
            for entry in entries
            if entry.case_id not in blocked_case_ids
            and (entry.smiles == smiles or entry.scaffold == case_scaffold)
        ]
        return filtered[:3]

    def load_strategy_hits(self, current_hypothesis: str | None = None) -> list[StrategyMemoryEntry]:
        entries = self._read_entries(self._strategy_path, StrategyMemoryEntry)
        if current_hypothesis is None:
            return entries[:3]
        filtered = [
            entry
            for entry in entries
            if current_hypothesis.lower() in entry.context_pattern.lower()
            or current_hypothesis.lower() in entry.reason.lower()
        ]
        return filtered[:3]

    def load_reliability_hits(self) -> list[ReliabilityMemoryEntry]:
        return self._read_entries(self._reliability_path, ReliabilityMemoryEntry)[:3]

    def write_case_entry(self, state: AieMasState) -> CaseMemoryEntry:
        key_supporting_evidence = [
            report.planner_readable_report
            for report in state.verifier_reports[-1:] + state.macro_reports[-1:] + state.microscopic_reports[-1:]
        ]
        entry = CaseMemoryEntry(
            case_id=state.case_id,
            smiles=state.smiles,
            scaffold=scaffold_proxy(state.smiles),
            initial_hypothesis=state.hypothesis_pool[0].name if state.hypothesis_pool else None,
            final_mechanism=state.current_hypothesis if state.finalize else None,
            final_confidence=state.confidence,
            key_supporting_evidence=key_supporting_evidence,
            key_conflicts=[
                state.latest_conflict_status
            ]
            if state.latest_conflict_status and state.latest_conflict_status != "none"
            else [],
            critical_turning_points=[entry.diagnosis_summary for entry in state.working_memory],
            useful_actions=[entry.action_taken for entry in state.working_memory],
            failed_actions=[],
            capability_lessons=[
                (
                    f"{candidate.agent_name}: {candidate.blocked_task_pattern} | "
                    f"{candidate.observed_limitation} | {candidate.recommended_contraction}"
                )
                for candidate in state.capability_lesson_candidates
            ],
            final_gt_source="deterministic_verifier_stub" if state.verifier_reports else None,
        )
        payload = self._read_json(self._case_path)
        payload.append(entry.model_dump(mode="json"))
        self._write_json(self._case_path, payload)
        return entry

    def _read_entries(self, path: Path, model_type: Any) -> list[Any]:
        payload = self._read_json(path)
        return [model_type.model_validate(item) for item in payload]

    def _read_json(self, path: Path) -> list[dict[str, Any]]:
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, path: Path, payload: list[dict[str, Any]]) -> None:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
