#!/usr/bin/env bash

# Copy this file to env/linux_llm.local.sh and adjust the values below.

export AIE_MAS_OPENAI_BASE_URL="http://34.13.73.248:3888/v1"
export AIE_MAS_OPENAI_MODEL="gpt-5.2"
export AIE_MAS_MICROSCOPIC_MODEL="gpt-4.1-mini"

# Set this if your OpenAI-compatible relay requires a key.
# export AIE_MAS_OPENAI_API_KEY="your-api-key"

export AIE_MAS_DATA_DIR="${AIE_MAS_PROJECT_ROOT}/var/data"
export AIE_MAS_MEMORY_DIR="${AIE_MAS_PROJECT_ROOT}/var/data/memory"
export AIE_MAS_LOG_DIR="${AIE_MAS_PROJECT_ROOT}/var/log"
export AIE_MAS_RUNTIME_DIR="${AIE_MAS_PROJECT_ROOT}/var/runtime"
export AIE_MAS_TOOLS_WORK_DIR="${AIE_MAS_PROJECT_ROOT}/var/runtime/tools"
