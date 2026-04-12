from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

ExecutionProfile = Literal["local-dev", "linux-prod"]
ToolBackend = Literal["real"]
PlannerBackend = Literal["openai_sdk"]
MicroscopicBackend = Literal["openai_sdk"]
MacroBackend = Literal["openai_sdk"]
VerifierBackend = Literal["openai_sdk"]
MicroscopicBudgetProfile = Literal["conservative", "balanced", "aggressive"]


def _default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


class AieMasConfig(BaseModel):
    project_root: Path = Field(default_factory=_default_project_root)
    execution_profile: ExecutionProfile = "local-dev"
    tool_backend: ToolBackend = "real"
    enable_long_term_memory: bool = False
    planner_backend: Optional[PlannerBackend] = None
    planner_base_url: str = "http://34.13.73.248:3888/v1"
    planner_model: str = "gpt-5.2"
    planner_api_key: Optional[str] = None
    planner_temperature: float = 0.0
    planner_timeout_seconds: float = 120.0
    microscopic_backend: Optional[MicroscopicBackend] = None
    microscopic_base_url: Optional[str] = None
    microscopic_model: Optional[str] = None
    microscopic_api_key: Optional[str] = None
    microscopic_temperature: Optional[float] = None
    microscopic_timeout_seconds: Optional[float] = None
    microscopic_budget_profile: Optional[MicroscopicBudgetProfile] = None
    macro_backend: Optional[MacroBackend] = None
    macro_base_url: Optional[str] = None
    macro_model: Optional[str] = None
    macro_api_key: Optional[str] = None
    macro_temperature: Optional[float] = None
    macro_timeout_seconds: Optional[float] = None
    verifier_backend: Optional[VerifierBackend] = None
    verifier_base_url: Optional[str] = None
    verifier_model: Optional[str] = None
    verifier_api_key: Optional[str] = None
    verifier_temperature: Optional[float] = None
    verifier_timeout_seconds: Optional[float] = None
    amesp_npara: Optional[int] = None
    amesp_maxcore_mb: Optional[int] = None
    amesp_use_ricosx: bool = True
    amesp_s1_nstates: Optional[int] = None
    amesp_td_tout: int = 1
    amesp_follow_up_max_conformers: Optional[int] = None
    amesp_follow_up_max_torsion_snapshots_total: Optional[int] = None
    amesp_probe_interval_seconds: float = 15.0
    prompts_dir: Optional[Path] = None
    data_dir: Optional[Path] = None
    memory_dir: Optional[Path] = None
    report_dir: Optional[Path] = None
    log_dir: Optional[Path] = None
    runtime_dir: Optional[Path] = None
    tools_work_dir: Optional[Path] = None
    atb_binary_path: Optional[Path] = None
    amesp_binary_path: Optional[Path] = None
    external_search_binary_path: Optional[Path] = None
    verifier_threshold: float = 0.72
    finalize_margin_threshold: float = 0.15
    max_rounds: int = 4

    @classmethod
    def from_env(cls, **overrides: Any) -> "AieMasConfig":
        env_values: dict[str, Any] = {}

        mapping = {
            "project_root": "AIE_MAS_PROJECT_ROOT",
            "execution_profile": "AIE_MAS_EXECUTION_PROFILE",
            "tool_backend": "AIE_MAS_TOOL_BACKEND",
            "enable_long_term_memory": "AIE_MAS_ENABLE_LONG_TERM_MEMORY",
            "planner_backend": "AIE_MAS_PLANNER_BACKEND",
            "planner_base_url": "AIE_MAS_OPENAI_BASE_URL",
            "planner_model": "AIE_MAS_OPENAI_MODEL",
            "planner_api_key": "AIE_MAS_OPENAI_API_KEY",
            "microscopic_backend": "AIE_MAS_MICROSCOPIC_BACKEND",
            "microscopic_base_url": "AIE_MAS_MICROSCOPIC_BASE_URL",
            "microscopic_model": "AIE_MAS_MICROSCOPIC_MODEL",
            "microscopic_api_key": "AIE_MAS_MICROSCOPIC_API_KEY",
            "microscopic_budget_profile": "AIE_MAS_MICROSCOPIC_BUDGET_PROFILE",
            "macro_backend": "AIE_MAS_MACRO_BACKEND",
            "macro_base_url": "AIE_MAS_MACRO_BASE_URL",
            "macro_model": "AIE_MAS_MACRO_MODEL",
            "macro_api_key": "AIE_MAS_MACRO_API_KEY",
            "verifier_backend": "AIE_MAS_VERIFIER_BACKEND",
            "verifier_base_url": "AIE_MAS_VERIFIER_BASE_URL",
            "verifier_model": "AIE_MAS_VERIFIER_MODEL",
            "verifier_api_key": "AIE_MAS_VERIFIER_API_KEY",
            "amesp_npara": "AIE_MAS_AMESP_NPARA",
            "amesp_maxcore_mb": "AIE_MAS_AMESP_MAXCORE_MB",
            "prompts_dir": "AIE_MAS_PROMPTS_DIR",
            "data_dir": "AIE_MAS_DATA_DIR",
            "memory_dir": "AIE_MAS_MEMORY_DIR",
            "report_dir": "AIE_MAS_REPORT_DIR",
            "log_dir": "AIE_MAS_LOG_DIR",
            "runtime_dir": "AIE_MAS_RUNTIME_DIR",
            "tools_work_dir": "AIE_MAS_TOOLS_WORK_DIR",
            "atb_binary_path": "AIE_MAS_ATB_BIN",
            "amesp_binary_path": "AIE_MAS_AMESP_BIN",
            "external_search_binary_path": "AIE_MAS_EXTERNAL_SEARCH_BIN",
        }
        path_fields = {
            "project_root",
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

        for field_name, env_name in mapping.items():
            raw_value = os.getenv(env_name)
            if raw_value:
                env_values[field_name] = Path(raw_value) if field_name in path_fields else raw_value

        if os.getenv("AIE_MAS_VERIFIER_THRESHOLD"):
            env_values["verifier_threshold"] = float(os.getenv("AIE_MAS_VERIFIER_THRESHOLD", "0.72"))
        if os.getenv("AIE_MAS_FINALIZE_MARGIN_THRESHOLD"):
            env_values["finalize_margin_threshold"] = float(
                os.getenv("AIE_MAS_FINALIZE_MARGIN_THRESHOLD", "0.15")
            )
        if os.getenv("AIE_MAS_MAX_ROUNDS"):
            env_values["max_rounds"] = int(os.getenv("AIE_MAS_MAX_ROUNDS", "4"))
        if os.getenv("AIE_MAS_ENABLE_LONG_TERM_MEMORY"):
            env_values["enable_long_term_memory"] = cls._parse_bool(
                os.getenv("AIE_MAS_ENABLE_LONG_TERM_MEMORY", "0")
            )
        if os.getenv("AIE_MAS_OPENAI_TEMPERATURE"):
            env_values["planner_temperature"] = float(os.getenv("AIE_MAS_OPENAI_TEMPERATURE", "0.0"))
        if os.getenv("AIE_MAS_OPENAI_TIMEOUT"):
            env_values["planner_timeout_seconds"] = float(os.getenv("AIE_MAS_OPENAI_TIMEOUT", "120.0"))
        if os.getenv("AIE_MAS_MICROSCOPIC_TEMPERATURE"):
            env_values["microscopic_temperature"] = float(
                os.getenv("AIE_MAS_MICROSCOPIC_TEMPERATURE", "0.0")
            )
        if os.getenv("AIE_MAS_MICROSCOPIC_TIMEOUT"):
            env_values["microscopic_timeout_seconds"] = float(
                os.getenv("AIE_MAS_MICROSCOPIC_TIMEOUT", "120.0")
            )
        if os.getenv("AIE_MAS_AMESP_S1_NSTATES"):
            env_values["amesp_s1_nstates"] = int(os.getenv("AIE_MAS_AMESP_S1_NSTATES", "5"))
        if os.getenv("AIE_MAS_AMESP_TD_TOUT"):
            env_values["amesp_td_tout"] = int(os.getenv("AIE_MAS_AMESP_TD_TOUT", "1"))
        if os.getenv("AIE_MAS_AMESP_FOLLOW_UP_MAX_CONFORMERS"):
            env_values["amesp_follow_up_max_conformers"] = int(
                os.getenv("AIE_MAS_AMESP_FOLLOW_UP_MAX_CONFORMERS", "3")
            )
        if os.getenv("AIE_MAS_AMESP_FOLLOW_UP_MAX_TORSION_SNAPSHOTS_TOTAL"):
            env_values["amesp_follow_up_max_torsion_snapshots_total"] = int(
                os.getenv("AIE_MAS_AMESP_FOLLOW_UP_MAX_TORSION_SNAPSHOTS_TOTAL", "6")
            )
        if os.getenv("AIE_MAS_MACRO_TEMPERATURE"):
            env_values["macro_temperature"] = float(os.getenv("AIE_MAS_MACRO_TEMPERATURE", "0.0"))
        if os.getenv("AIE_MAS_MACRO_TIMEOUT"):
            env_values["macro_timeout_seconds"] = float(os.getenv("AIE_MAS_MACRO_TIMEOUT", "120.0"))
        if os.getenv("AIE_MAS_VERIFIER_TEMPERATURE"):
            env_values["verifier_temperature"] = float(os.getenv("AIE_MAS_VERIFIER_TEMPERATURE", "0.1"))
        if os.getenv("AIE_MAS_VERIFIER_TIMEOUT"):
            env_values["verifier_timeout_seconds"] = float(
                os.getenv("AIE_MAS_VERIFIER_TIMEOUT", "600.0")
            )
        if os.getenv("AIE_MAS_AMESP_USE_RICOSX"):
            env_values["amesp_use_ricosx"] = cls._parse_bool(
                os.getenv("AIE_MAS_AMESP_USE_RICOSX", "1")
            )
        if os.getenv("AIE_MAS_AMESP_PROBE_INTERVAL"):
            env_values["amesp_probe_interval_seconds"] = float(
                os.getenv("AIE_MAS_AMESP_PROBE_INTERVAL", "15.0")
            )

        for key, value in overrides.items():
            if value is not None:
                env_values[key] = value

        return cls(**env_values)

    def model_post_init(self, __context: object) -> None:
        self.project_root = self.project_root.expanduser().resolve()

        if self.planner_backend is None:
            self.planner_backend = "openai_sdk"
        if self.microscopic_backend is None:
            self.microscopic_backend = "openai_sdk"
        if self.microscopic_base_url is None:
            self.microscopic_base_url = self.planner_base_url
        if self.microscopic_model is None:
            self.microscopic_model = "gpt-4.1-mini"
        if self.microscopic_api_key is None:
            self.microscopic_api_key = self.planner_api_key
        if self.microscopic_temperature is None:
            self.microscopic_temperature = self.planner_temperature
        if self.microscopic_timeout_seconds is None:
            self.microscopic_timeout_seconds = self.planner_timeout_seconds
        if self.microscopic_budget_profile is None:
            self.microscopic_budget_profile = "balanced"
        if self.macro_backend is None:
            self.macro_backend = "openai_sdk"
        if self.macro_base_url is None:
            self.macro_base_url = self.microscopic_base_url
        if self.macro_model is None:
            self.macro_model = self.microscopic_model
        if self.macro_api_key is None:
            self.macro_api_key = self.microscopic_api_key
        if self.macro_temperature is None:
            self.macro_temperature = self.microscopic_temperature
        if self.macro_timeout_seconds is None:
            self.macro_timeout_seconds = self.microscopic_timeout_seconds
        if self.verifier_backend is None:
            self.verifier_backend = "openai_sdk"
        if self.verifier_base_url is None:
            self.verifier_base_url = "https://openrouter.ai/api/v1"
        if self.verifier_model is None:
            self.verifier_model = "anthropic/claude-3.5-sonnet"
        if self.verifier_temperature is None:
            self.verifier_temperature = 0.1
        if self.verifier_timeout_seconds is None:
            self.verifier_timeout_seconds = 600.0
        if self.amesp_s1_nstates is None:
            self.amesp_s1_nstates = {
                "conservative": 3,
                "balanced": 5,
                "aggressive": 8,
            }[self.microscopic_budget_profile]
        if self.amesp_follow_up_max_conformers is None:
            self.amesp_follow_up_max_conformers = {
                "conservative": 2,
                "balanced": 3,
                "aggressive": 5,
            }[self.microscopic_budget_profile]
        if self.amesp_follow_up_max_torsion_snapshots_total is None:
            self.amesp_follow_up_max_torsion_snapshots_total = {
                "conservative": 4,
                "balanced": 6,
                "aggressive": 8,
            }[self.microscopic_budget_profile]
        if self.amesp_npara is None:
            if self.execution_profile == "linux-prod":
                self.amesp_npara = max(1, min(20, os.cpu_count() or 1))
            else:
                self.amesp_npara = 4
        if self.amesp_maxcore_mb is None:
            self.amesp_maxcore_mb = 12000 if self.execution_profile == "linux-prod" else 2000

        if self.prompts_dir is None:
            self.prompts_dir = Path("src") / "aie_mas" / "prompts"
        if self.data_dir is None:
            self.data_dir = Path("var") / "data"
        if self.memory_dir is None:
            self.memory_dir = self.data_dir / "memory"
        if self.report_dir is None:
            self.report_dir = Path("var") / "reports"
        if self.log_dir is None:
            self.log_dir = Path("var") / "log"
        if self.runtime_dir is None:
            self.runtime_dir = Path("var") / "runtime"
        if self.tools_work_dir is None:
            self.tools_work_dir = self.runtime_dir / "tools"

        self.prompts_dir = self._resolve_path(self.prompts_dir)
        self.data_dir = self._resolve_path(self.data_dir)
        self.memory_dir = self._resolve_path(self.memory_dir)
        self.report_dir = self._resolve_path(self.report_dir)
        self.log_dir = self._resolve_path(self.log_dir)
        self.runtime_dir = self._resolve_path(self.runtime_dir)
        self.tools_work_dir = self._resolve_path(self.tools_work_dir)
        self.atb_binary_path = self._resolve_optional_path(self.atb_binary_path)
        self.amesp_binary_path = self._resolve_optional_path(self.amesp_binary_path)
        self.external_search_binary_path = self._resolve_optional_path(
            self.external_search_binary_path
        )
        if self.amesp_binary_path is None:
            default_amesp_bin = (self.project_root / "third_party" / "Amesp" / "Bin" / "amesp").resolve()
            if default_amesp_bin.exists():
                self.amesp_binary_path = default_amesp_bin

    def ensure_runtime_dirs(self) -> None:
        runtime_dirs = [self.data_dir, self.report_dir, self.log_dir, self.runtime_dir, self.tools_work_dir]
        if self.enable_long_term_memory:
            runtime_dirs.append(self.memory_dir)
        for path in runtime_dirs:
            if path is not None:
                path.mkdir(parents=True, exist_ok=True)

    def assert_supported_runtime(self) -> None:
        return None

    def runtime_context(self) -> dict[str, Any]:
        from aie_mas.tools.macro import MACRO_CAPABILITY_REGISTRY
        from aie_mas.tools.cli_execution import render_cli_command_catalog

        return {
            "execution_profile": self.execution_profile,
            "tool_backend": self.tool_backend,
            "enable_long_term_memory": self.enable_long_term_memory,
            "planner_backend": self.planner_backend,
            "planner_base_url": self.planner_base_url,
            "planner_model": self.planner_model,
            "planner_api_key_configured": bool(self.planner_api_key),
            "microscopic_backend": self.microscopic_backend,
            "microscopic_base_url": self.microscopic_base_url,
            "microscopic_model": self.microscopic_model,
            "microscopic_api_key_configured": bool(self.microscopic_api_key),
            "microscopic_temperature": self.microscopic_temperature,
            "microscopic_timeout_seconds": self.microscopic_timeout_seconds,
            "microscopic_budget_profile": self.microscopic_budget_profile,
            "macro_backend": self.macro_backend,
            "macro_base_url": self.macro_base_url,
            "macro_model": self.macro_model,
            "macro_api_key_configured": bool(self.macro_api_key),
            "macro_temperature": self.macro_temperature,
            "macro_timeout_seconds": self.macro_timeout_seconds,
            "macro_supported_scope": list(MACRO_CAPABILITY_REGISTRY.keys()),
            "macro_capability_registry": {
                name: {
                    "purpose": definition.purpose,
                    "structure_target": definition.structure_target,
                    "supported_deliverables": list(definition.supported_deliverables),
                    "evidence_goal_tags": list(definition.evidence_goal_tags),
                    "exact_observable_tags": list(definition.exact_observable_tags),
                    "unsupported_requests_note": definition.unsupported_requests_note,
                }
                for name, definition in MACRO_CAPABILITY_REGISTRY.items()
            },
            "macro_command_catalog": render_cli_command_catalog("macro"),
            "microscopic_command_catalog": render_cli_command_catalog("microscopic"),
            "verifier_backend": self.verifier_backend,
            "verifier_base_url": self.verifier_base_url,
            "verifier_model": self.verifier_model,
            "verifier_api_key_configured": bool(self.verifier_api_key),
            "verifier_temperature": self.verifier_temperature,
            "verifier_timeout_seconds": self.verifier_timeout_seconds,
            "amesp_npara": self.amesp_npara,
            "amesp_maxcore_mb": self.amesp_maxcore_mb,
            "amesp_use_ricosx": self.amesp_use_ricosx,
            "amesp_s1_nstates": self.amesp_s1_nstates,
            "amesp_td_tout": self.amesp_td_tout,
            "amesp_follow_up_max_conformers": self.amesp_follow_up_max_conformers,
            "amesp_follow_up_max_torsion_snapshots_total": self.amesp_follow_up_max_torsion_snapshots_total,
            "amesp_probe_interval_seconds": self.amesp_probe_interval_seconds,
            "project_root": str(self.project_root),
            "prompts_dir": str(self.prompts_dir),
            "data_dir": str(self.data_dir),
            "memory_dir": str(self.memory_dir),
            "report_dir": str(self.report_dir),
            "log_dir": str(self.log_dir),
            "runtime_dir": str(self.runtime_dir),
            "tools_work_dir": str(self.tools_work_dir),
            "atb_binary_path": str(self.atb_binary_path) if self.atb_binary_path else None,
            "amesp_binary_path": str(self.amesp_binary_path) if self.amesp_binary_path else None,
            "external_search_binary_path": (
                str(self.external_search_binary_path)
                if self.external_search_binary_path
                else None
            ),
            "planner_temperature": self.planner_temperature,
            "planner_timeout_seconds": self.planner_timeout_seconds,
            "verifier_threshold": self.verifier_threshold,
            "finalize_margin_threshold": self.finalize_margin_threshold,
            "max_rounds": self.max_rounds,
        }

    def _resolve_path(self, path: Path) -> Path:
        candidate = path.expanduser()
        if candidate.is_absolute():
            return candidate.resolve()
        return (self.project_root / candidate).resolve()

    def _resolve_optional_path(self, path: Optional[Path]) -> Optional[Path]:
        if path is None:
            return None
        return self._resolve_path(path)

    @staticmethod
    def _parse_bool(raw_value: str) -> bool:
        return raw_value.strip().lower() in {"1", "true", "yes", "on"}
