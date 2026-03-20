# PROJECT_SPEC.md

## 一、系统架构

AIE-MAS 是一个由 Planner 主导的闭环多智能体系统。

核心流程：

User Query  
→ Planner 生成 hypothesis pool  
→ 选择当前主假设  
→ 调用 Microscopic / Macro / Verifier 中的一个或多个结果型 agent  
→ 获取模板化结果  
→ Planner 进行 diagnosis  
→ Planner 输出下一步 action  
→ 更新 working memory  
→ 进入下一轮  
→ 最终输出结论并写入 long-term memory

## 二、模块职责

### Planner
唯一思考模块。

输入：
- 用户问题
- working memory 摘要
- 当前主假设
- Microscopic / Macro / Verifier 的模板化结果
- 必要时的 long-term memory 摘要

输出：
- diagnosis
- action
- 当前主假设更新
- confidence
- 是否需要 verifier
- 是否 finalize

### Microscopic Agent
结果型 agent，不做推理。

职责：
- 接收 Planner 指定的微观任务
- 调用微观工具
- 返回结果模板

第一轮固定任务：
- S0 optimization
- S1 optimization

### Macro Agent
结果型 agent，不做推理。

职责：
- 接收 Planner 指定的结构/经验任务
- 调用低成本工具
- 返回结果模板

### Verifier
结果型 agent，不做推理。

职责：
- 接收 Planner 指定的外部监督任务
- 检索外部证据
- 生成 evidence cards
- 返回结果模板

## 三、非 Planner agent 输出协议

所有非 Planner agent 都必须返回：

1. `task_received`
2. `tool_calls`
3. `raw_results`
4. `structured_results`
5. `status`
6. `planner_readable_report`

其中：
- `planner_readable_report` 仅用于结果陈述
- 不允许加入机制判断或动作建议

## 四、Planner 输出协议

Planner 每轮必须输出：

### 1. Diagnosis
说明：
- 当前主假设是什么
- 上一轮新增了什么结果
- 这些结果对当前主假设意味着什么
- 当前还不能判断的地方是什么
- 当前最关键缺口是什么

### 2. Action
说明：
- 下一步调用哪个 agent
- 当前目标是什么
- 为什么现在是这个动作

## 五、Memory 设计

### Working Memory
用于当前 case 内的多轮 refine，防止 Planner 遗忘。

每条 round summary 至少包括：
- `round_id`
- `current_hypothesis`
- `confidence`
- `action_taken`
- `evidence_summary`
- `diagnosis_summary`
- `main_gap`
- `conflict_status`
- `next_action`

### Long-term Memory
用于跨案例经验积累，分为三类：

#### Case Memory
- 分子
- 初始假设
- 最终机制
- 关键证据
- 关键冲突
- 有效动作
- 失败动作
- GT 来源

#### Strategy Memory
- 某类局面下什么动作有效
- 什么情况下不应过早 finalize
- 什么证据组合通常意味着什么

#### Reliability Memory
- 哪类证据源更可信
- 哪类相似性线索易误导
- 哪类微观结果更稳定
- 哪类冲突经常是伪冲突

## 六、Graph 设计要求

建议至少包含以下节点：

1. `ingest_user_query`
2. `planner_initial`
3. `run_macro`
4. `run_microscopic`
5. `planner_diagnosis`
6. `run_verifier`
7. `planner_reweight_or_finalize`
8. `update_working_memory`
9. `update_long_term_memory`
10. `final_output`

## 七、路由规则

### 第一轮
必须运行：
- Macro Agent
- Microscopic Agent

### 中间轮
由 Planner 在 diagnosis 后决定：
- 继续 Macro
- 继续 Microscopic
- 调用 Verifier

### 高置信规则
若当前主假设置信度超过阈值，则下一步必须调用 Verifier。

### 切换机制规则
只有在 Verifier 返回之后，Planner 才能决定是否切换主假设。

## 八、当前阶段要求

当前阶段虽然无法接入全部真实 agent 能力，但架构必须直接按最终版设计。

允许：
- mock Microscopic
- mock Macro
- mock Verifier

不允许：
- 为了临时跑通而破坏最终版职责边界