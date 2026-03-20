# AIE-MAS

AIE-MAS 是一个基于 LangGraph + LangChain 的多智能体系统，用于围绕输入分子的 SMILES 表达式，对其发光机制进行逐轮推理、验证与诊断。

本项目从一开始就按最终理想架构设计，而不是作为一个长期不断增加新功能和修补的原型系统。当前阶段虽然暂时无法第一时间接入全部真实 scientific runtime 和外部 agent 能力，但代码框架必须直接按照最终系统边界搭建，后续仅替换具体实现，不重构核心架构。

## 项目目标

输入：
- 用户问题
- 一个目标分子的 SMILES

输出：
- 当前最可能的发光机制
- 一段 diagnosis
- 证据链摘要
- 当前结论的不确定性
- 必要时的下一步建议

## 系统核心思想

AIE-MAS 不是一个多个 agent 各自思考、相互辩论的开放式系统。

它是一个由 Planner 主导的、围绕单一主假设逐轮 refine 的闭环系统：

User Query  
→ Planner 生成 hypothesis pool  
→ 选择当前主假设  
→ 调用 Microscopic / Macro / Verifier 中的一个或多个结果型 agent  
→ 获取模板化结果  
→ Planner 输出 diagnosis  
→ Planner 决定下一步 action  
→ 更新 working memory  
→ 进入下一轮  
→ 最终输出结论并写入 long-term memory

## 核心模块

系统包含四个核心 agent：

1. Planner
2. Microscopic Agent
3. Macro Agent
4. Verifier

另外包含两个关键 memory 模块：

- Working Memory
- Long-term Memory

## 职责分工

### Planner
唯一负责推理与决策的 agent。

职责包括：
- 理解用户任务
- 生成 hypothesis pool
- 选择当前主假设
- 读取其他 agent 的模板化结果
- 输出 diagnosis
- 决定下一步 action
- 在 verifier 返回外部监督后决定是否重排 hypothesis

### Microscopic Agent
不负责思考。只负责：
- 接收 Planner 指定的任务
- 调用微观计算工具
- 返回模板化结果

第一轮固定执行：
- S0 optimization
- S1 optimization

### Macro Agent
不负责思考。只负责：
- 接收 Planner 指定的任务
- 调用低成本结构/经验工具
- 返回模板化结果

### Verifier
不负责思考。只负责：
- 接收 Planner 指定的外部监督任务
- 检索外部证据
- 构造 evidence cards
- 返回模板化结果

## 关键原则

1. 只有 Planner 负责思考  
2. 单轮只服务当前主假设  
3. 第一轮固定基础微观计算  
4. Verifier 不需要每轮调用，但高置信时必须强制调用  
5. 机制切换主要发生在 Verifier 之后  

## Memory 设计原则

### Working Memory
服务当前 case，用于防止多轮 refine 中遗忘。  
每轮由 Planner 写入一条 round summary。

### Long-term Memory
服务跨 case 经验积累，包含：
- Case Memory
- Strategy Memory
- Reliability Memory

## 当前开发目标

当前阶段不要求接通全部真实 scientific tools。  
但项目骨架必须直接按照最终理想架构搭建：

- LangGraph 工作流
- Planner 主导的闭环
- 模板化结果协议
- working memory / long-term memory 结构
- mock tools 占位
- 后续只替换实现，不改变架构

## 技术栈

- Python 3.11+
- LangGraph
- LangChain
- Pydantic
- Pytest

## 运行环境

运行约束以 `RUNTIME_ENV.md` 为准。

- 本地开发环境：macOS，默认用于 mock graph、smoke test、schema/prompt/routing 验证
- 远端运行环境：Linux，默认用于安装真实依赖、接入真实 tool wrapper、运行完整工作流

当前第一阶段代码已经区分：

- `execution_profile=local-dev | linux-prod`
- `tool_backend=mock | real`

说明：

- 当前仓库已经支持 `local-dev + mock`
- 当前仓库也支持 `linux-prod + mock` 作为远端部署前的最小闭环验证
- `linux-prod + real` 的入口已预留，但真实 scientific wrapper 仍待后续接入

## 路径配置

以下路径都可以通过 CLI 参数或环境变量覆盖：

- `prompts_dir` / `AIE_MAS_PROMPTS_DIR`
- `data_dir` / `AIE_MAS_DATA_DIR`
- `memory_dir` / `AIE_MAS_MEMORY_DIR`
- `log_dir` / `AIE_MAS_LOG_DIR`
- `runtime_dir` / `AIE_MAS_RUNTIME_DIR`
- `tools_work_dir` / `AIE_MAS_TOOLS_WORK_DIR`
- `atb_binary_path` / `AIE_MAS_ATB_BIN`
- `amesp_binary_path` / `AIE_MAS_AMESP_BIN`
- `external_search_binary_path` / `AIE_MAS_EXTERNAL_SEARCH_BIN`

如果不显式指定，默认会落在项目根目录下的跨平台相对路径：

- `var/data`
- `var/data/memory`
- `var/log`
- `var/runtime`
- `var/runtime/tools`

## 本地 Mock 运行

推荐方式：

```bash
python3 -m pip install -e ".[dev]"
python3 run_case.py \
  --smiles 'C(c1ccccc1)(c1ccccc1)=C(c1ccccc1)c1ccccc1' \
  --execution-profile local-dev \
  --tool-backend mock
```

也可以安装后用包级 CLI：

```bash
aie-mas-run-case \
  --smiles 'C(c1ccccc1)(c1ccccc1)=C(c1ccccc1)c1ccccc1' \
  --execution-profile local-dev \
  --tool-backend mock
```

## 远端 Linux 运行

当前第一阶段推荐用 Linux 部署配置跑 mock backend，确保 git pull 后即可运行：

```bash
git pull
python3 -m pip install -e ".[linux-runtime]"
export AIE_MAS_EXECUTION_PROFILE=linux-prod
export AIE_MAS_TOOL_BACKEND=mock
export AIE_MAS_DATA_DIR=var/data
export AIE_MAS_MEMORY_DIR=var/data/memory
export AIE_MAS_LOG_DIR=var/log
export AIE_MAS_RUNTIME_DIR=var/runtime
aie-mas-run-case --smiles 'C(c1ccccc1)(c1ccccc1)=C(c1ccccc1)c1ccccc1'
```

如果暂时不安装包，也可以直接在仓库根目录运行：

```bash
python3 run_case.py \
  --smiles 'C(c1ccccc1)(c1ccccc1)=C(c1ccccc1)c1ccccc1' \
  --execution-profile linux-prod \
  --tool-backend mock
```

未来接入真实 Linux wrapper 后，保持同一 graph / state / prompt / memory 结构，只需把 `tool_backend` 切到 `real` 并配置真实二进制路径。
