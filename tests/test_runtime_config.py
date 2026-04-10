from __future__ import annotations

from pathlib import Path

import pytest

from aie_mas.config import AieMasConfig
from aie_mas.graph.builder import build_graph, normalize_graph_result
from aie_mas.graph.state import AieMasState


def test_config_paths_are_resolved_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AIE_MAS_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("AIE_MAS_EXECUTION_PROFILE", "linux-prod")
    monkeypatch.setenv("AIE_MAS_TOOL_BACKEND", "real")
    monkeypatch.setenv("AIE_MAS_PLANNER_BACKEND", "openai_sdk")
    monkeypatch.setenv("AIE_MAS_OPENAI_BASE_URL", "http://34.13.73.248:3888/v1")
    monkeypatch.setenv("AIE_MAS_OPENAI_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("AIE_MAS_MACRO_BACKEND", "openai_sdk")
    monkeypatch.setenv("AIE_MAS_MACRO_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("AIE_MAS_VERIFIER_BACKEND", "openai_sdk")
    monkeypatch.setenv("AIE_MAS_VERIFIER_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("AIE_MAS_VERIFIER_MODEL", "anthropic/claude-3.5-sonnet")
    monkeypatch.setenv("AIE_MAS_VERIFIER_API_KEY", "test-verifier-key")
    monkeypatch.setenv("AIE_MAS_MICROSCOPIC_BACKEND", "openai_sdk")
    monkeypatch.setenv("AIE_MAS_MICROSCOPIC_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("AIE_MAS_AMESP_NPARA", "22")
    monkeypatch.setenv("AIE_MAS_AMESP_MAXCORE_MB", "24000")
    monkeypatch.setenv("AIE_MAS_AMESP_USE_RICOSX", "1")
    monkeypatch.setenv("AIE_MAS_AMESP_S1_NSTATES", "5")
    monkeypatch.setenv("AIE_MAS_AMESP_TD_TOUT", "1")
    monkeypatch.setenv("AIE_MAS_MICROSCOPIC_BUDGET_PROFILE", "balanced")
    monkeypatch.setenv("AIE_MAS_AMESP_FOLLOW_UP_MAX_CONFORMERS", "3")
    monkeypatch.setenv("AIE_MAS_AMESP_FOLLOW_UP_MAX_TORSION_SNAPSHOTS_TOTAL", "6")
    monkeypatch.setenv("AIE_MAS_AMESP_PROBE_INTERVAL", "5")
    monkeypatch.setenv("AIE_MAS_DATA_DIR", "runtime_data")
    monkeypatch.setenv("AIE_MAS_MEMORY_DIR", "runtime_data/memory_store")
    monkeypatch.setenv("AIE_MAS_REPORT_DIR", "runtime_reports")
    monkeypatch.setenv("AIE_MAS_LOG_DIR", "runtime_logs")
    monkeypatch.setenv("AIE_MAS_RUNTIME_DIR", "runtime_workspace")
    monkeypatch.setenv("AIE_MAS_ENABLE_LONG_TERM_MEMORY", "1")

    config = AieMasConfig.from_env()
    config.ensure_runtime_dirs()

    assert config.execution_profile == "linux-prod"
    assert config.tool_backend == "real"
    assert config.enable_long_term_memory is True
    assert config.planner_backend == "openai_sdk"
    assert config.microscopic_backend == "openai_sdk"
    assert config.planner_base_url == "http://34.13.73.248:3888/v1"
    assert config.planner_model == "gpt-4.1-mini"
    assert config.macro_backend == "openai_sdk"
    assert config.macro_model == "gpt-4.1-mini"
    assert config.macro_base_url == "http://34.13.73.248:3888/v1"
    assert config.verifier_backend == "openai_sdk"
    assert config.verifier_base_url == "https://openrouter.ai/api/v1"
    assert config.verifier_model == "anthropic/claude-3.5-sonnet"
    assert config.verifier_api_key == "test-verifier-key"
    assert config.microscopic_base_url == "http://34.13.73.248:3888/v1"
    assert config.microscopic_model == "gpt-4.1-mini"
    assert config.amesp_npara == 22
    assert config.amesp_maxcore_mb == 24000
    assert config.amesp_use_ricosx is True
    assert config.microscopic_budget_profile == "balanced"
    assert config.amesp_s1_nstates == 5
    assert config.amesp_td_tout == 1
    assert config.amesp_follow_up_max_conformers == 3
    assert config.amesp_follow_up_max_torsion_snapshots_total == 6
    assert config.amesp_probe_interval_seconds == 5.0
    assert config.data_dir == (tmp_path / "runtime_data").resolve()
    assert config.memory_dir == (tmp_path / "runtime_data" / "memory_store").resolve()
    assert config.report_dir == (tmp_path / "runtime_reports").resolve()
    assert config.log_dir == (tmp_path / "runtime_logs").resolve()
    assert config.runtime_dir == (tmp_path / "runtime_workspace").resolve()
    assert config.tools_work_dir == (tmp_path / "runtime_workspace" / "tools").resolve()
    assert config.memory_dir.exists()
    assert config.report_dir.exists()
    assert config.log_dir.exists()
    assert config.runtime_dir.exists()


def test_config_skips_memory_dir_when_long_term_memory_is_disabled(tmp_path: Path) -> None:
    config = AieMasConfig(
        project_root=tmp_path,
        execution_profile="local-dev",
        enable_long_term_memory=False,
    )

    config.ensure_runtime_dirs()

    assert config.data_dir.exists()
    assert config.report_dir.exists()
    assert config.log_dir.exists()
    assert config.runtime_dir.exists()
    assert not config.memory_dir.exists()


def test_real_backend_can_build_graph_with_real_microscopic_support(tmp_path: Path) -> None:
    config = AieMasConfig(
        project_root=tmp_path,
        execution_profile="linux-prod",
        tool_backend="real",
    )

    graph = build_graph(config)

    assert graph is not None


def test_normalize_graph_result_accepts_langgraph_dict_output() -> None:
    state = AieMasState(
        user_query="Assess the likely AIE mechanism for this molecule.",
        smiles="C1=CC=CC=C1",
        final_answer={"current_hypothesis": "placeholder"},
        state_snapshot={"ok": True},
    )

    normalized = normalize_graph_result(state.model_dump(mode="json"))

    assert isinstance(normalized, AieMasState)
    assert normalized.final_answer == {"current_hypothesis": "placeholder"}
    assert normalized.state_snapshot == {"ok": True}


def test_planner_backend_defaults_follow_execution_profile(tmp_path: Path) -> None:
    local_config = AieMasConfig(project_root=tmp_path, execution_profile="local-dev")
    linux_config = AieMasConfig(project_root=tmp_path, execution_profile="linux-prod")

    assert local_config.planner_backend == "openai_sdk"
    assert linux_config.planner_backend == "openai_sdk"
    assert local_config.microscopic_backend == "openai_sdk"
    assert linux_config.microscopic_backend == "openai_sdk"
    assert local_config.planner_model == "gpt-5.2"
    assert linux_config.planner_model == "gpt-5.2"
    assert local_config.macro_backend == "openai_sdk"
    assert linux_config.macro_backend == "openai_sdk"
    assert local_config.verifier_backend == "openai_sdk"
    assert linux_config.verifier_backend == "openai_sdk"
    assert local_config.verifier_model == "anthropic/claude-3.5-sonnet"
    assert linux_config.verifier_model == "anthropic/claude-3.5-sonnet"
    assert local_config.verifier_base_url == "https://openrouter.ai/api/v1"
    assert linux_config.verifier_base_url == "https://openrouter.ai/api/v1"
    assert local_config.microscopic_model == "gpt-4.1-mini"
    assert linux_config.microscopic_model == "gpt-4.1-mini"
    assert local_config.microscopic_base_url == local_config.planner_base_url
    assert linux_config.microscopic_base_url == linux_config.planner_base_url
    assert local_config.macro_model == local_config.microscopic_model
    assert linux_config.macro_model == linux_config.microscopic_model
    assert local_config.macro_base_url == local_config.microscopic_base_url
    assert linux_config.macro_base_url == linux_config.microscopic_base_url
    assert local_config.macro_temperature == local_config.microscopic_temperature
    assert linux_config.macro_temperature == linux_config.microscopic_temperature
    assert local_config.macro_timeout_seconds == local_config.microscopic_timeout_seconds
    assert linux_config.macro_timeout_seconds == linux_config.microscopic_timeout_seconds
    assert local_config.amesp_maxcore_mb == 2000
    assert linux_config.amesp_maxcore_mb == 12000
    assert local_config.amesp_use_ricosx is True
    assert linux_config.amesp_use_ricosx is True
    assert local_config.microscopic_budget_profile == "balanced"
    assert linux_config.microscopic_budget_profile == "balanced"
    assert local_config.amesp_s1_nstates == 5
    assert linux_config.amesp_s1_nstates == 5
    assert local_config.amesp_follow_up_max_conformers == 3
    assert linux_config.amesp_follow_up_max_conformers == 3
    assert local_config.amesp_follow_up_max_torsion_snapshots_total == 6
    assert linux_config.amesp_follow_up_max_torsion_snapshots_total == 6
    assert local_config.amesp_probe_interval_seconds == 15.0
    assert linux_config.amesp_probe_interval_seconds == 15.0


def test_linux_real_defaults_cap_parallelism_for_amesp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("aie_mas.config.os.cpu_count", lambda: 22)

    config = AieMasConfig(project_root=tmp_path, execution_profile="linux-prod")

    assert config.amesp_npara == 20
