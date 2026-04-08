# 发现与决策

## 需求
- 将近期 AIE-MAS 的工程修复、probe 结果、典型 case 分析整理成可供后续 paper-writing agent 使用的持久化 Markdown 文档。
- 重点不是复述所有对话，而是保留：
  - 关键工程问题
  - 关键修复里程碑
  - 代表性报告与科学结论
  - 明确的 caveat / 未完成事项

## 研究发现
- Amesp orbital analysis 最初失败，不是因为 binary 完全不支持，而是实现把 `lmo` / `natorb` 放错到了 `>ope`；按手册改到 `>method` 后，`LMO` 与 `natorb no` 可以工作，`UNO/NSO` 只适用于 `U` 体系。
- microscopic capability surface 目前已经基本打通：baseline、targeted charge/density/transition dipole/RIS/localized orbital/natural orbital 均可执行；大部分 CT 相关输出仍是 proxy 级证据，这属于能力边界，不是调用错误。
- `run_targeted_localized_orbital_analysis` / `run_targeted_natural_orbital_analysis` 的恢复，证明“probe + 最小输入验证 + 语法矩阵”是定位科学软件接口问题的有效方法。
- 后续主要工程问题从“接口调用错误”转移到了：
  - addressability 不足
  - targeted follow-up artifact 不能复用
  - pairwise / closure bookkeeping 不一致
  - summary 导出丢字段
- 针对 torsion targeting，问题从“找不到目标就直接失败”变成“可以自动 relax 并继续跑”，但仍存在“想测 donor-aryl，实际落到 fallback rotor”的语义命中不准问题。
- Portfolio-first screening 与 portfolio-neutral framing 的引入，主要是为了解决：
  - 第三候选机制被静默遗忘
  - 第一轮 top1 漂移被过早放大成后续调查偏差
- 对 benchmark 标签本身，已经出现至少两个值得警惕的 case：
  - `CSMPP`：数据集标签 `TICT` 真实性存疑，当前证据更偏 `ICT`
  - `Pyren-Sal`：看起来像 ESIPT 高疑似，但旧流程会过早收缩到 `ICT/TICT`

## 技术决策
| 决策 | 理由 |
|------|------|
| 用 probe 脚本而不是直接反复跑完整 case 定位 Amesp 问题 | 能把“工具语法错误”和“Planner 决策问题”分开 |
| 为 targeted follow-up 注册正式 artifact bundle | 让下轮能精确引用中间产物，而不是靠自然语言回指 |
| 给 torsion discovery 增加 soft-preference + relax ladder | 防止 Planner 的软偏好被硬过滤放大成 `precondition_missing` |
| 引入 portfolio-first screening gate | 避免系统只围绕 top1/top2 工作，漏掉仍可信但未直接筛查的候选机制 |
| 在 screening 阶段将 specialized agents 改为 `portfolio_neutral` framing | 避免第一轮 top1 漂移过度影响后续任务 framing |
| 在 OpenAI-compatible client 增加 transient retry/backoff | 解决 planner/macro/micro/verifier 遇到上游 5xx/reset 时整个 workflow 直接崩掉的问题 |

## 遇到的问题
| 问题 | 解决方案 |
|------|---------|
| baseline probe 在 Linux 上报 `Please chechk the PATH environmental variable of Amesp` | 在 Amesp subprocess 环境里自动注入 `Bin` 目录到 `PATH` |
| localized/natural orbital follow-up 被误回退到 `aTB` | 把 `ground_state_profile` 正确传进 single-point follow-up |
| `lmo` / `natorb` 在 probe 中一直报 `error keyword in >ope!` | 通过手册与最小 probe 确认应写入 `>method`，不是 `>ope` |
| targeted charge summary 错把 `mulliken_charges` 记成缺失 | 收紧默认 scope，让 summary 与真实 deliverables 对齐 |
| Planner 要求的 member 级 / follow-up 产物级操作无法稳定表达 | 新增 exact member targeting、bundle member listing、follow-up artifact bundle 注册 |
| torsion selection policy 太严导致关键扭转实验根本没跑 | 改成 rank-first + relax ladder，而非 filter-first |
| 第三候选机制在流程中过早消失 | 引入 `coverage_debt_hypotheses` 和 portfolio-first gate |
| 第一轮 top1 漂移被过早放大 | 在 portfolio screening 阶段把 task framing 从 `current_hypothesis` 解耦 |
| 上游 LLM 网关 transient 5xx/reset 会直接打断 workflow | 在 OpenAI-compatible client 里增加有限重试与退避 |

## 资源
- 关键 handoff 文档：
  - `paper_handoff.md`
  - `task_plan.md`
  - `findings.md`
  - `progress.md`
- 关键提交：
  - `c8ab613 Restore orbital analysis capabilities with method blocks`
  - `283d75d Add bundle member targeting and report consistency`
  - `a24429d Add soft-preference torsion target relaxation`
  - `9c1aafa Add portfolio-first hypothesis screening gate`
  - `e65844a Decouple portfolio screening from top1 anchoring`
  - `3344b1e Retry transient upstream LLM failures`
- 关键 report / probe：
  - `debug_reports/ope_keyword_probe_20260407-162100-342895_035ae145e418`
  - `debug_reports/ope_syntax_matrix_probe_20260407-162107-670709_cd37cb2a2bdf`
  - `debug_reports/20260407-164329-917043_13c501618e2d`
  - `debug_reports/20260407-224117-498454_c2bc515913ed`
  - `debug_reports/20260408-005227-267635_794777cbae87`
  - `debug_reports/20260408-014029-796056_02c40d4000af`
  - `debug_reports/20260408-172338-988361_4c805753ef9d`
  - `debug_reports/20260408-191354-976854_6c2dc6241578`

## 视觉/浏览器发现
- 本次整理未做新的网页/浏览器检索；主要来源为本地代码、提交记录和本地 `debug_reports/`

---
*每执行2次查看/浏览器/搜索操作后更新此文件*
*防止视觉信息丢失*
