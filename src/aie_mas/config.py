from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

ExecutionProfile = Literal["local-dev", "linux-prod"]
ToolBackend = Literal["mock", "real"]
PlannerBackend = Literal["mock", "openai_sdk"]


def _default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


class AieMasConfig(BaseModel):
    project_root: Path = Field(default_factory=_default_project_root)
    execution_profile: ExecutionProfile = "local-dev"
    tool_backend: ToolBackend = "mock"
    enable_long_term_memory: bool = False
    planner_backend: Optional[PlannerBackend] = None
    planner_base_url: str = "http://34.13.73.248:3888/v1"
    planner_model: str = "gpt-4.1-mini"
    planner_api_key: Optional[str] = None
    planner_temperature: float = 0.0
    planner_timeout_seconds: float = 120.0
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

        for key, value in overrides.items():
            if value is not None:
                env_values[key] = value

        return cls(**env_values)

    def model_post_init(self, __context: object) -> None:
        self.project_root = self.project_root.expanduser().resolve()

        if self.planner_backend is None:
            self.planner_backend = "mock" if self.execution_profile == "local-dev" else "openai_sdk"

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

    def ensure_runtime_dirs(self) -> None:
        runtime_dirs = [self.data_dir, self.report_dir, self.log_dir, self.runtime_dir, self.tools_work_dir]
        if self.enable_long_term_memory:
            runtime_dirs.append(self.memory_dir)
        for path in runtime_dirs:
            if path is not None:
                path.mkdir(parents=True, exist_ok=True)

    def assert_supported_runtime(self) -> None:
        if self.tool_backend == "real":
            raise NotImplementedError(
                "The real tool backend is reserved for future Linux wrappers and is not "
                "implemented in the current first-stage code. Use tool_backend='mock' for now."
            )

    def runtime_context(self) -> dict[str, Any]:
        return {
            "execution_profile": self.execution_profile,
            "tool_backend": self.tool_backend,
            "enable_long_term_memory": self.enable_long_term_memory,
            "planner_backend": self.planner_backend,
            "planner_base_url": self.planner_base_url,
            "planner_model": self.planner_model,
            "planner_api_key_configured": bool(self.planner_api_key),
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
