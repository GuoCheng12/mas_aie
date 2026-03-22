#!/usr/bin/env bash

AIE_MAS_ENV_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
AIE_MAS_PROJECT_ROOT_DEFAULT="$(cd -- "${AIE_MAS_ENV_DIR}/.." && pwd)"

export AIE_MAS_PROJECT_ROOT="${AIE_MAS_PROJECT_ROOT:-${AIE_MAS_PROJECT_ROOT_DEFAULT}}"

if [ -f "${AIE_MAS_ENV_DIR}/amesp.local.sh" ]; then
  . "${AIE_MAS_ENV_DIR}/amesp.local.sh"
fi

export AIE_MAS_AMESP_ROOT="${AIE_MAS_AMESP_ROOT:-${AIE_MAS_PROJECT_ROOT}/third_party/Amesp}"
export AIE_MAS_PYAMESP_ROOT="${AIE_MAS_PYAMESP_ROOT:-${AIE_MAS_PROJECT_ROOT}/third_party/PyAmesp}"
export AIE_MAS_AMESP_BIN="${AIE_MAS_AMESP_BIN:-${AIE_MAS_AMESP_ROOT}/Bin/amesp}"

if [ -d "${AIE_MAS_AMESP_ROOT}/Bin" ]; then
  export PATH="${AIE_MAS_AMESP_ROOT}/Bin:${PATH}"
fi

if [ -d "${AIE_MAS_PYAMESP_ROOT}" ]; then
  if [ -n "${PYTHONPATH:-}" ]; then
    export PYTHONPATH="${AIE_MAS_PYAMESP_ROOT}:${PYTHONPATH}"
  else
    export PYTHONPATH="${AIE_MAS_PYAMESP_ROOT}"
  fi
fi

export KMP_STACKSIZE="${KMP_STACKSIZE:-4g}"
export ASE_AMESP_COMMAND="${ASE_AMESP_COMMAND:-${AIE_MAS_AMESP_BIN} PREFIX.aip PREFIX.aop}"
export AMESP_COMMAND="${AMESP_COMMAND:-${AIE_MAS_AMESP_BIN} }"
