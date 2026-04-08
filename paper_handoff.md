# AIE-MAS 近期开发与实验 handoff

## 1. 这份文档是干什么的
这份文档是给后续单独线程的 paper-writing agent 的主入口。它的目标不是复现所有对话，而是把近期最重要的：

- 工程修复主线
- 代表性 probe / case 的证据链
- 现在已经比较稳定的结论
- 还需要保留的 caveat

整理成一个可直接继续工作的摘要。

建议后续线程优先读取顺序：
1. `paper_handoff.md`
2. `findings.md`
3. `progress.md`
4. 代表性 `debug_reports/`
5. 对应提交 diff

## 2. 核心主线概述
近期工作的主线可以分成 6 段：

1. **把 microscopic capability surface 真正打通**
   - 从一开始 baseline/probe 都可能在 Linux 上挂掉，到后来 baseline、targeted charge/density/transition dipole/RIS/localized orbital/natural orbital 都能跑通。

2. **用 probe 脚本把 Amesp orbital analysis 的真实语法找对**
   - 一开始误以为 `lmo` / `natorb` 在 `>ope`
   - 后来通过手册、binary probe、keyword probe、syntax matrix probe 反复确认：
     - `lmo` / `natorb` 应该放在 `>method`
     - `nlmo` 才在 `>ope`
     - `natorb no` 可用
     - `uno/nso` 只适用于 `U`

3. **把 agent-tool addressability 做到“可引用中间产物”**
   - 给 bundle/member 增加稳定寻址
   - 让 targeted follow-up 产物也注册为正式 artifact bundle
   - 让后续 inspection 能真正引用这些中间产物

4. **修 torsion targeting，不再因为选择策略太严直接挂掉**
   - 从 `filter-first` 改到 `rank-first`
   - 增加 relax ladder
   - 允许 fallback，而不是轻易 `precondition_missing`

5. **修流程层面的 hypothesis handling**
   - 先加 `portfolio-first screening`
   - 再把 `portfolio_screening` 阶段从 `current_hypothesis` 解耦
   - 核心目的：不要让第一轮 top1 的漂移过早绑死后续 agent framing

6. **补 runtime 稳定性**
   - OpenAI-compatible LLM client 现在能对 transient 5xx/reset/timeout 做有限重试和退避

## 3. 关键提交与作用

| 提交 | 作用 |
|------|------|
| `c8ab613` | 恢复 orbital analysis capability，并按正确 block 生成 Amesp 输入 |
| `ba3518f` | 修 `run_targeted_charge_analysis` 的 summary bookkeeping |
| `283d75d` | 增加 bundle member targeting、follow-up artifact bundle、report consistency |
| `a24429d` | 增加 soft-preference torsion target relaxation |
| `9c1aafa` | 增加 portfolio-first hypothesis screening gate |
| `e65844a` | 在 screening 阶段将 task framing 从 top1 anchoring 解耦 |
| `9893bc3` | 补齐 screening framing schema 漏项 |
| `3344b1e` | 为 OpenAI-compatible LLM client 增加 transient upstream retry/backoff |

## 4. Amesp / microscopic capability 这条线最重要的结论

### 4.1 初期问题
最初的问题不是单一 bug，而是一串链式问题：

- baseline/probe 在 Linux 上找不到 `amesp`
- targeted single-point follow-up 的 `ground_state_profile` 没传到底
- orbital routes 被错误写成 `>ope lmo...` / `>ope natorb...`

### 4.2 probe 证明了什么
最有代表性的报告是：

- `debug_reports/ope_keyword_probe_20260407-151419-001372_1173a16283c4`
- `debug_reports/amesp_binary_probe_20260407-152818-857911_46f376ac536b`
- `debug_reports/ope_syntax_matrix_probe_20260407-154028-142812_d077ce4221ee`
- `debug_reports/ope_keyword_probe_20260407-162100-342895_035ae145e418`
- `debug_reports/ope_syntax_matrix_probe_20260407-162107-670709_cd37cb2a2bdf`

这条线最终得出的稳定结论是：

- `lmo pm`：可用
- `lmo boys`：可用
- `natorb no`：可用
- `natorb uno`：闭壳层测试分子不可用，报 only works for U
- `natorb nso`：闭壳层测试分子不可用，报 only works for U

这意味着：
- 之前“暂时下线 orbital capability”是一个中间性的保守措施
- 后来恢复 capability 是合理的，因为问题并不是 binary 完全不支持，而是我们的 block placement 错了

### 4.3 当前边界
要注意当前仍然有边界：

- 很多 route 的证据仍是 proxy-level，不是决定性的 CT-number / e-h separation / Δμ
- orbital capability 的可用性目前主要验证到：
  - `LMO`
  - `natorb no`
- `UNO/NSO` 没有作为默认路径重新开放

## 5. 代表性 case 及其意义

### 5.1 `0e0dc6d0a0d5`：能力面基本打通后的完整 case
报告：
- `debug_reports/20260407-165813-880657_0e0dc6d0a0d5`

意义：
- Planner 已经能真正调用恢复后的 new capability surface
- 最终给出 `ICT`，证据链主要依赖：
  - baseline
  - torsion snapshots
  - targeted state / RIS / orbital / charge 这些 follow-up

它证明的重点不是“化学上 100% 正确”，而是：
- **接口层已经可用**
- **Planner 不会因为 orbital route 再直接报错**

### 5.2 `1673a169870a`：reporting/bookkeeping 基本改善
报告：
- `debug_reports/20260407-214437-202097_1673a169870a`

意义：
- 说明新的 summary / action labels / pairwise bookkeeping 改动已经开始起效
- 但仍能看到个别 closure evidence-source 不完全一致的残留问题

### 5.3 `c2bc515913ed`（CSMPP）：benchmark 标签真实性问题
报告：
- `debug_reports/20260407-224117-498454_c2bc515913ed`

当前判断：
- benchmark 标签是 `TICT`
- 但这轮内部 baseline + torsion + verifier 证据整体更支持 `ICT`
- 因而这个标签至少应视为 **disputed / questionable gold**

要点：
- 这不是简单“模型跑错”
- 而是系统已经能产出足够强的反标签证据链

### 5.4 `794777cbae87`：soft-preference torsion targeting 的效果与剩余问题
报告：
- `debug_reports/20260408-005227-267635_794777cbae87`

当前判断：
- 新的 soft-preference / relax ladder 已经让系统不再因为找不到 donor-aryl rotor 就直接失败
- 但仍可能出现：
  - 想测 donor-aryl
  - 实际选到 fallback rotor

所以这一轮的意义是：
- **从“硬失败”升级到了“能跑但 semantic targeting 还不够准”**

### 5.5 `02c40d4000af`（Pyren-Sal）：ESIPT 高疑似 case 暴露 hypothesis framing 问题
报告：
- `debug_reports/20260408-014029-796056_02c40d4000af`

这是近期最重要的流程性 case 之一。

核心问题：
- 这个分子结构上非常像 ESIPT 候选
- 但系统早期流程仍会快速收缩到 `ICT/TICT`
- 实际没有公平地对 `ESIPT` 做 direct screening

它直接促成了：
- `portfolio-first screening`
- `portfolio_screening` 阶段不再被 `current_hypothesis` 强锚定

### 5.6 `4c805753ef9d` vs `6c2dc6241578`：同一分子第一轮 top1 漂移
报告：
- `debug_reports/20260408-172338-988361_4c805753ef9d`
- `debug_reports/20260408-191354-976854_6c2dc6241578`

意义：
- 第一轮 top1 不稳定本身并不稀奇
- 真正的问题是旧流程会把这个不稳定 top1 过早放大成 specialized-agent framing 差异

这对 paper/总结非常重要，因为它说明：
- 问题不只是 LLM 漂移
- 而是**流程把早期漂移放大了**

## 6. 当前已解决的问题

### 6.1 已基本解决
- Amesp PATH/runtime 基础问题
- targeted single-point route profile 误传 / 漏传
- orbital capability block placement 错误
- follow-up capability surface 接口可用性
- bundle/member targeting 与 follow-up artifact registration
- torsion discovery 的硬失败问题
- portfolio-first screening gate
- screening 阶段去 top1 anchoring
- transient upstream LLM failure retry

### 6.2 仍未完全解决
- donor-aryl / N-aryl 这类高层语义与实际 torsion metadata 的稳定映射
- verifier 失败后的 circuit breaker/重试策略是否够好
- 个别 closure bookkeeping / evidence-source 字段的一致性残留
- `ESIPT`、`ICT`、`TICT` 等机制的 screening coverage 是否已经在更多 benchmark case 上系统验证

## 7. 对后续写 paper 最有价值的叙事骨架

可以考虑把故事写成下面这种结构：

1. **问题背景**
   - 多 agent + quantum-chemistry tool orchestration 在 AIE 机制判别中的主要难点，不只是模型推理，还包括 capability routing、artifact reuse、workflow gate 与 runtime reliability

2. **工程贡献**
   - 从 probe 驱动出发，把 microscopic capability surface 从“概念存在”变成“真实可用”
   - 通过 addressability、follow-up artifact reuse、soft-preference targeting、portfolio-first screening，逐步缩小系统性误差来源

3. **方法论贡献**
   - 用最小 probe / syntax matrix / binary introspection 去定位 scientific software 接口问题
   - 不把化学规则硬编码进 Python，而是通过流程约束提升 Planner 推理的公平性和稳定性

4. **案例分析**
   - `CSMPP`: benchmark label challenge
   - `Pyren-Sal`: ESIPT coverage gap and workflow redesign
   - 一到两个 capability-recovery case：证明 orbital routes 与 targeted follow-ups 已经能进入真实 case

5. **限制与 caveat**
   - 当前很多内部 observables 仍是 proxy
   - verifier 服务稳定性会影响路径
   - 某些机制的 decisive evidence 仍依赖后续工具能力提升

## 8. 后续 paper-writing 线程应优先做什么

建议后续线程按这个顺序继续：

1. 读取本文件
2. 读取 `findings.md`
3. 读取 `progress.md`
4. 针对下面 4 组材料做细读：
   - `debug_reports/ope_keyword_probe_20260407-162100-342895_035ae145e418`
   - `debug_reports/ope_syntax_matrix_probe_20260407-162107-670709_cd37cb2a2bdf`
   - `debug_reports/20260407-224117-498454_c2bc515913ed`
   - `debug_reports/20260408-014029-796056_02c40d4000af`
5. 如需要写“工程修复时间线”，再补读：
   - `git log --oneline --decorate -20`

## 9. 明确 caveat，避免过度表述
- 不要把 proxy-level observables 写成 decisive CT metrics
- 不要把 `CSMPP` 直接写成“已证明 benchmark 标签错误”，更稳妥的是“label authenticity is questionable / disputed under current evidence”
- 不要把 `Pyren-Sal` 写成“已证明不是 ESIPT”；更准确是“旧流程未对 ESIPT 做公平 screening，因此暴露了 hypothesis framing 缺口”
- 不要把 orbital capability 写成“所有 natural orbital modes fully supported”；更准确是：
  - `LMO` 可用
  - `natorb no` 可用
  - `UNO/NSO` 对闭壳层默认路径不适用

## 10. 一句话结论
近期这条开发线的真正成果不是“某几个 case 终于给出某个标签”，而是：

**AIE-MAS 的多 agent + microscopic capability + workflow gate 现在已经从“容易被接口/流程问题带偏”推进到了“能够用更可审计、更可复用、更少早期偏置放大的方式调查机制假设”。**
