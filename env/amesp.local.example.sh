#!/usr/bin/env bash

# Copy this file to env/amesp.local.sh and adjust the values below for
# your Linux runtime.

export AIE_MAS_AMESP_ROOT="${AIE_MAS_PROJECT_ROOT}/third_party/Amesp"
export AIE_MAS_PYAMESP_ROOT="${AIE_MAS_PROJECT_ROOT}/third_party/PyAmesp"
export AIE_MAS_AMESP_BIN="${AIE_MAS_AMESP_ROOT}/Bin/amesp"

# Keep the explicit command form for newer ASE versions.
export ASE_AMESP_COMMAND="${AIE_MAS_AMESP_BIN} PREFIX.aip PREFIX.aop"

# Amesp manual recommends a large OpenMP stack.
export KMP_STACKSIZE="4g"
