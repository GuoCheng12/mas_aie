# AGENTS.md

本仓库用于构建 AIE-MAS。请严格遵守以下规则。

## 一、总体原则

这是一个最终版架构优先的项目，不是一个通过不断补丁和频繁重构逐步长出来的原型系统。

当前如果某些真实工具或 agent 能力无法接入，请使用 mock / stub 占位，但不要改变系统边界。

## 二、系统规则

### 1. 只有 Planner 负责推理与决策
Planner 是唯一负责思考的 agent。

Microscopic、Macro、Verifier 都不应承担推理职责，它们只负责：
- 接收任务
- 调用工具
- 返回结果模板

### 2. 单轮只围绕当前主假设工作
系统每一轮只服务当前主假设。  
机制切换只能在 Verifier 返回外部监督后由 Planner 决定。

### 3. 第一轮固定流程
第一轮必须至少调用：
- Microscopic Agent（执行 S0/S1 opt）
- Macro Agent（执行低成本结构/经验分析）

### 4. 高置信必须调用 Verifier
如果 Planner 判断当前主假设置信度足以支持临时结论，则下一步必须强制调用 Verifier。

## 三、工程规则

### 1. 使用 LangGraph 作为主工作流框架
- 显式建图
- 不要使用黑箱 agent executor 替代主流程控制

### 2. LangChain 只用于模型、prompt、tools 抽象
- 模型封装、prompt 处理、tool 包装可使用 LangChain
- 工作流调度必须放在 LangGraph

### 3. Prompt 必须独立存放
- 所有 prompt 放在 `src/aie_mas/prompts/`
- 不要在 Python 文件中硬编码长 prompt

### 4. Tools 与 agents 解耦
- agent 节点不直接内嵌复杂工具逻辑
- 所有工具封装在 `src/aie_mas/tools/`

### 5. 所有非 Planner agent 必须返回模板化结果
每个非 Planner agent 的输出必须至少包含：
- `task_received`
- `tool_calls`
- `raw_results`
- `structured_results`
- `status`
- `planner_readable_report`
注意：
- `planner_readable_report` 只能陈述结果
- 不允许包含机制判断、动作建议或推理


### 6. Runtime environment
- 开发环境默认是 macOS
- 真实运行环境默认是远端 Linux
- 请阅读并遵守 `RUNTIME_ENV.md`
- 不要将本机路径或本机环境假设硬编码进实现


### 6. Planner 的输出必须包含两部分
- `diagnosis`
- `action`

## 四、Memory 规则

### Working Memory
- 每一轮结束后必须写入一条 Planner round summary
- 用于下一轮继续推理
- working memory 优先级高于 long-term memory

### Long-term Memory
必须预留三类结构：
- Case Memory
- Strategy Memory
- Reliability Memory

## 五、当前阶段允许与不允许

当前阶段允许：
- mock tools
- mock verifier evidence
- mock micro/macro outputs

当前阶段不要求：
- 真实 Amesp / aTB runtime
- 真实 embodied 实验
- 完整文献检索系统

但必须保证：
- graph 已按最终版结构搭好
- 后续只替换实现，不改架构

## 六、代码要求

- Python 3.11+
- 使用 Pydantic 定义 state 和 report schema
- 类型标注清晰
- 所有关键决策写入 state
- 至少提供 smoke test

## 七、禁止事项

- 不要让 Microscopic / Macro / Verifier 参与推理
- 不要把 Verifier 做成直接裁决器
- 不要把 working memory 简化成原始聊天记录堆积
- 不要为了临时跑通而破坏最终版职责边界