from __future__ import annotations

from pathlib import Path

import pytest

from aie_mas.config import AieMasConfig
from aie_mas.graph.builder import build_graph, normalize_graph_result
from aie_mas.graph.state import AieMasState


def test_config_paths_are_resolved_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AIE_MAS_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("AIE_MAS_EXECUTION_PROFILE", "linux-prod")
    monkeypatch.setenv("AIE_MAS_TOOL_BACKEND", "mock")
    monkeypatch.setenv("AIE_MAS_DATA_DIR", "runtime_data")
    monkeypatch.setenv("AIE_MAS_MEMORY_DIR", "runtime_data/memory_store")
    monkeypatch.setenv("AIE_MAS_LOG_DIR", "runtime_logs")
    monkeypatch.setenv("AIE_MAS_RUNTIME_DIR", "runtime_workspace")

    config = AieMasConfig.from_env()
    config.ensure_runtime_dirs()

    assert config.execution_profile == "linux-prod"
    assert config.tool_backend == "mock"
    assert config.data_dir == (tmp_path / "runtime_data").resolve()
    assert config.memory_dir == (tmp_path / "runtime_data" / "memory_store").resolve()
    assert config.log_dir == (tmp_path / "runtime_logs").resolve()
    assert config.runtime_dir == (tmp_path / "runtime_workspace").resolve()
    assert config.tools_work_dir == (tmp_path / "runtime_workspace" / "tools").resolve()
    assert config.memory_dir.exists()
    assert config.log_dir.exists()
    assert config.runtime_dir.exists()


def test_real_backend_is_reserved_for_future_linux_wrappers(tmp_path: Path) -> None:
    config = AieMasConfig(
        project_root=tmp_path,
        execution_profile="linux-prod",
        tool_backend="real",
    )

    with pytest.raises(NotImplementedError):
        build_graph(config)


def test_normalize_graph_result_accepts_langgraph_dict_output() -> None:
    state = AieMasState(
        user_query="Assess the likely AIE mechanism for this molecule.",
        smiles="C1=CC=CC=C1",
        final_answer={"current_hypothesis": "mock"},
        state_snapshot={"ok": True},
    )

    normalized = normalize_graph_result(state.model_dump(mode="json"))

    assert isinstance(normalized, AieMasState)
    assert normalized.final_answer == {"current_hypothesis": "mock"}
    assert normalized.state_snapshot == {"ok": True}
