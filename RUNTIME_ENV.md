# RUNTIME_ENV.md

## 1. 开发与运行模式

本项目采用 **本地开发 + 远端 Linux 运行** 的双环境模式。

### 本地环境
- 操作系统：macOS
- 主要用途：
  - 编写代码
  - 修改项目结构
  - 维护 prompts / schemas / graph / memory / tool interfaces
  - 运行轻量 smoke tests
  - 使用 mock tools 做最小闭环验证

### 远端环境
- 操作系统：Linux
- 主要用途：
  - 安装真实依赖
  - 运行真实 LangGraph / LangChain 环境
  - 接入未来真实 scientific runtime
  - 执行 aTB / Amesp / 其他量化化学工具
  - 执行需要 Linux 环境的完整实验

## 2. Codex 必须遵守的环境假设

### 2.1 不要假设本机必须能跑真实 scientific runtime
Codex 必须默认认为：
- macOS 本机不负责安装完整 Linux/scientific runtime
- 本机不能作为 aTB / Amesp / 未来真实计算工具的最终运行环境
- 本机代码运行目标以 mock、兼容、轻量验证为主

### 2.2 所有真实运行必须面向 Linux 可部署
Codex 后续新增任何真实依赖、脚本、wrapper、命令行入口时，必须优先考虑：
- Linux 可运行
- Linux 路径与环境变量可配置
- 不将 macOS 本地路径、Homebrew 路径、用户目录硬编码进项目逻辑

### 2.3 本地与远端通过 Git 同步
默认工作流为：

1. 在本地 macOS 修改代码
2. 提交到 Git 仓库
3. 在远端 Linux `git pull`
4. 在远端 Linux 安装/更新依赖并运行真实流程

Codex 在写文档、脚本、说明时，应默认这种工作流。

---

## 3. 路径与配置要求

### 3.1 禁止硬编码本机绝对路径
禁止在代码中写死类似：
- `/Users/...`
- macOS 特定目录
- 本机临时目录作为默认长期存储路径

### 3.2 所有关键路径必须可配置
以下路径必须通过配置项、环境变量或 CLI 参数指定：
- memory 存储目录
- prompt 目录
- data 目录
- log 目录
- 未来 scientific tools 的工作目录
- 外部工具二进制路径

### 3.3 默认配置应尽量跨平台
当前阶段默认行为应满足：
- 本地 macOS 可用 mock 模式跑 smoke test
- 远端 Linux 可替换真实依赖后继续运行
- 不因平台不同而改变架构与状态结构

---

## 4. 依赖策略

### 4.1 当前阶段
当前阶段允许：
- mock planner
- mock macro / microscopic / verifier tools
- compatibility shim
- 轻量本地测试

### 4.2 后续阶段
后续接入真实能力时：
- 真实 LangGraph / LangChain 依赖优先在 Linux 安装与验证
- aTB / Amesp / 外部 scientific runtime 仅以 Linux 为主要目标环境
- 若某依赖在 macOS 上安装困难，不应因此改变系统架构

### 4.3 Codex 写依赖时的原则
Codex 后续修改 `pyproject.toml`、shell 脚本、安装说明时，应遵守：
- 将“本地开发依赖”和“Linux 运行依赖”区分开
- 不强迫本机安装完整 scientific runtime
- 优先保留 mock / fallback 模式

---

## 5. 测试与运行分层

### 5.1 本地 macOS 应支持
- 单元测试
- smoke test
- mock graph 跑通
- schema / prompt / routing 验证

### 5.2 远端 Linux 应支持
- 真实依赖安装
- 真实工作流运行
- 真实工具 wrapper 调用
- 真实 memory / data / runtime integration

### 5.3 Codex 后续新增测试时
应尽量区分：
- 本地可跑测试
- Linux 专用集成测试

不要把必须依赖 Linux scientific runtime 的测试混进默认 smoke test。

---

## 6. 工程实现约束

### 6.1 真实工具接入必须走 wrapper
未来接入：
- aTB
- Amesp
- 外部检索
- 其他 Linux-only 工具

都必须通过独立 wrapper / adapter 层，不允许直接散落在 agent 逻辑中。

### 6.2 agent / graph / memory 架构不得因平台差异改变
平台差异只应影响：
- tool implementation
- runtime config
- dependency installation
- path settings

不得影响：
- Planner 角色
- 非 Planner agent 的职责边界
- AieMasState 结构
- working memory / long-term memory 结构
- graph 主流程

---

## 7. Codex 后续工作时的默认行为

Codex 在后续任务中应默认：

- 本地环境 = macOS 开发环境
- 远端环境 = Linux 真实运行环境
- 代码必须保持 Linux 可部署
- 若某功能需要真实 runtime，先设计接口，再允许 mock 占位
- 若必须写运行说明，优先写 Linux 版本，并补充本地 mock 用法

---

## 8. 当前推荐工作流

### 本地
- 修改代码
- 跑 mock smoke test
- 提交 Git

### 远端 Linux
- `git pull`
- 安装依赖
- 配置环境变量
- 运行真实流程
- 调试真实工具链

这是本项目后续默认工作模式。