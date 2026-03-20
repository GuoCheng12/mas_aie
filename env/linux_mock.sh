#!/usr/bin/env bash

AIE_MAS_ENV_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
AIE_MAS_PROJECT_ROOT_DEFAULT="$(cd -- "${AIE_MAS_ENV_DIR}/.." && pwd)"

export AIE_MAS_PROJECT_ROOT="${AIE_MAS_PROJECT_ROOT:-${AIE_MAS_PROJECT_ROOT_DEFAULT}}"

if [ -f "${AIE_MAS_ENV_DIR}/linux_mock.local.sh" ]; then
  # User-specific overrides live here and are not tracked by Git.
  . "${AIE_MAS_ENV_DIR}/linux_mock.local.sh"
fi

export AIE_MAS_EXECUTION_PROFILE="${AIE_MAS_EXECUTION_PROFILE:-linux-prod}"
export AIE_MAS_TOOL_BACKEND="${AIE_MAS_TOOL_BACKEND:-mock}"
export AIE_MAS_PROMPTS_DIR="${AIE_MAS_PROMPTS_DIR:-${AIE_MAS_PROJECT_ROOT}/src/aie_mas/prompts}"
export AIE_MAS_DATA_DIR="${AIE_MAS_DATA_DIR:-${AIE_MAS_PROJECT_ROOT}/var/data}"
export AIE_MAS_MEMORY_DIR="${AIE_MAS_MEMORY_DIR:-${AIE_MAS_PROJECT_ROOT}/var/data/memory}"
export AIE_MAS_LOG_DIR="${AIE_MAS_LOG_DIR:-${AIE_MAS_PROJECT_ROOT}/var/log}"
export AIE_MAS_RUNTIME_DIR="${AIE_MAS_RUNTIME_DIR:-${AIE_MAS_PROJECT_ROOT}/var/runtime}"
export AIE_MAS_TOOLS_WORK_DIR="${AIE_MAS_TOOLS_WORK_DIR:-${AIE_MAS_PROJECT_ROOT}/var/runtime/tools}"
