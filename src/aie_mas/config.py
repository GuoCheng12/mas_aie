from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

ExecutionProfile = Literal["local-dev", "linux-prod"]
ToolBackend = Literal["mock", "real"]


def _default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


class AieMasConfig(BaseModel):
    project_root: Path = Field(default_factory=_default_project_root)
    execution_profile: ExecutionProfile = "local-dev"
    tool_backend: ToolBackend = "mock"
    prompts_dir: Optional[Path] = None
    data_dir: Optional[Path] = None
    memory_dir: Optional[Path] = None
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
            "prompts_dir": "AIE_MAS_PROMPTS_DIR",
            "data_dir": "AIE_MAS_DATA_DIR",
            "memory_dir": "AIE_MAS_MEMORY_DIR",
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

        for key, value in overrides.items():
            if value is not None:
                env_values[key] = value

        return cls(**env_values)

    def model_post_init(self, __context: object) -> None:
        self.project_root = self.project_root.expanduser().resolve()

        if self.prompts_dir is None:
            self.prompts_dir = Path("src") / "aie_mas" / "prompts"
        if self.data_dir is None:
            self.data_dir = Path("var") / "data"
        if self.memory_dir is None:
            self.memory_dir = self.data_dir / "memory"
        if self.log_dir is None:
            self.log_dir = Path("var") / "log"
        if self.runtime_dir is None:
            self.runtime_dir = Path("var") / "runtime"
        if self.tools_work_dir is None:
            self.tools_work_dir = self.runtime_dir / "tools"

        self.prompts_dir = self._resolve_path(self.prompts_dir)
        self.data_dir = self._resolve_path(self.data_dir)
        self.memory_dir = self._resolve_path(self.memory_dir)
        self.log_dir = self._resolve_path(self.log_dir)
        self.runtime_dir = self._resolve_path(self.runtime_dir)
        self.tools_work_dir = self._resolve_path(self.tools_work_dir)
        self.atb_binary_path = self._resolve_optional_path(self.atb_binary_path)
        self.amesp_binary_path = self._resolve_optional_path(self.amesp_binary_path)
        self.external_search_binary_path = self._resolve_optional_path(
            self.external_search_binary_path
        )

    def ensure_runtime_dirs(self) -> None:
        for path in (self.data_dir, self.memory_dir, self.log_dir, self.runtime_dir, self.tools_work_dir):
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
            "project_root": str(self.project_root),
            "prompts_dir": str(self.prompts_dir),
            "data_dir": str(self.data_dir),
            "memory_dir": str(self.memory_dir),
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
