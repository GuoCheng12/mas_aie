from __future__ import annotations

import json
from pathlib import Path

from aie_mas.cli.run_case import run_case_workflow


def test_current_case_does_not_hit_its_own_case_memory(tmp_path: Path) -> None:
    memory_dir = tmp_path / "memory"
    smiles = "C(c1ccccc1)(c1ccccc1)=C(c1ccccc1)c1ccccc1"

    first_state = run_case_workflow(
        smiles=smiles,
        user_query="Assess the likely AIE mechanism for this molecule.",
        execution_profile="local-dev",
        planner_backend="mock",
        tool_backend="mock",
        prompts_dir=Path(__file__).resolve().parents[1] / "src" / "aie_mas" / "prompts",
        data_dir=tmp_path / "data",
        memory_dir=memory_dir,
        log_dir=tmp_path / "log",
        runtime_dir=tmp_path / "runtime",
    )

    assert first_state.finalize is True
    assert first_state.case_memory_hits == []

    case_memory_payload = json.loads((memory_dir / "case_memory.json").read_text(encoding="utf-8"))
    assert len(case_memory_payload) == 1
    assert case_memory_payload[0]["case_id"] == first_state.case_id

    second_state = run_case_workflow(
        smiles=smiles,
        user_query="Assess the likely AIE mechanism for this molecule again.",
        execution_profile="local-dev",
        planner_backend="mock",
        tool_backend="mock",
        prompts_dir=Path(__file__).resolve().parents[1] / "src" / "aie_mas" / "prompts",
        data_dir=tmp_path / "data_2",
        memory_dir=memory_dir,
        log_dir=tmp_path / "log_2",
        runtime_dir=tmp_path / "runtime_2",
    )

    assert len(second_state.case_memory_hits) == 1
    assert second_state.case_memory_hits[0].case_id == first_state.case_id
