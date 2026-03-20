#!/usr/bin/env bash

# Copy this file to env/linux_mock.local.sh and adjust the values below.
# The local override file is ignored by Git.

export AIE_MAS_DATA_DIR="${AIE_MAS_PROJECT_ROOT}/var/data"
export AIE_MAS_MEMORY_DIR="${AIE_MAS_PROJECT_ROOT}/var/data/memory"
export AIE_MAS_LOG_DIR="${AIE_MAS_PROJECT_ROOT}/var/log"
export AIE_MAS_RUNTIME_DIR="${AIE_MAS_PROJECT_ROOT}/var/runtime"
export AIE_MAS_TOOLS_WORK_DIR="${AIE_MAS_PROJECT_ROOT}/var/runtime/tools"

# Future Linux-only tool wrappers can be configured here.
# export AIE_MAS_ATB_BIN="/path/to/atb"
# export AIE_MAS_AMESP_BIN="/path/to/amesp"
