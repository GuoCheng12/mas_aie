#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

. "${PROJECT_ROOT}/env/linux_mock.sh"

exec python "${PROJECT_ROOT}/run_case.py" "$@"
