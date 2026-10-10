# 第 1 讲：什么是智能体（Agent）

## 教学目标

1. 理解"裸 LLM"在数学任务上的三类典型失效，知道为什么需要智能体；
2. 掌握智能体的定义与五个构成要素：目标、模型、工具、记忆、控制循环；
3. 能区分**工作流（workflow）**与**智能体（agent）**两种不同的编排方式；
4. 通过一个真实案例（Rethlas 生成智能体）看懂一份 agent 的"岗位说明书"长什么样。

## 时间分配

| 环节 | 时间 |
| --- | --- |
| 导入：裸 LLM 做数学的三个翻车现场 | 8 分钟 |
| 智能体的定义与五要素 | 12 分钟 |
| 工作流 vs 智能体；Coding Agent 形态 | 8 分钟 |
| 案例解剖：Rethlas 生成智能体的 AGENTS.md | 12 分钟 |
| 小结与课堂讨论 | 5 分钟 |

---

## 一、导入：裸 LLM 做数学为什么不可靠

### 三个翻车现场

**1. 算术与代数幻觉。** 让模型直接口算 $x^4-2$ 在 $\mathbb{Q}$ 上的分裂域次数、一个大整数分解、一个群的不变量，它经常给出"看起来很像真的"的错误答案。模型没有执行能力，一切"计算"都是文本联想。

**2. 证明不可靠。** 模型写的证明可能每一步都像数学，但整体有致命漏洞：循环论证、偷换量词、引用不存在的定理。没有人检查，错误就会一路滚到最后。

**3. 无法与环境交互。** 真正的数学工作要查文献、跑 SageMath/OSQP、编译 Lean、翻自己的笔记。裸模型没有手，什么都做不了。

> **课堂提问**：你让 ChatGPT 做过的数学任务里，哪次它错得最离谱？（2 分钟，2–3 个学生分享）

### 核心观点

LLM 是一个很强的**推理引擎**，但要完成真实数学任务，它必须被嵌入一个更大的系统：能调用工具执行、能留存中间结论、能被检查纠错、能持续迭代。这个系统就是**智能体**。

---

## 二、智能体的定义与五要素

### 定义

> **智能体（Agent）**：一个以 LLM 为决策核心，围绕明确目标，自主地"观察—思考—行动—再观察"循环运行，直到目标达成或停止条件满足的系统。

经典运行循环（常称 agent loop / ReAct 式循环）：

```
┌──────────────────────────────────────────┐
│  观察(Observe) ← 行动结果、新信息          │
│       ↓                                  │
│  思考(Think)：LLM 根据目标与上下文决策      │
│       ↓                                  │
│  行动(Act)：调用工具 / 写文件 / 提问        │
│       ↓                                  │
│  记录(Remember)：中间结论持久化             │
└─────── 未达标 → 回到观察；达标 → 终止 ──────┘
```

### 五要素（板书/幻灯片核心图）

| 要素 | 作用 | 数学智能体中的典型形态 |
| --- | --- | --- |
| **目标（Goal）** | 定义"什么叫完成" | "为 data/problem.md 产出一份通过验证的证明蓝图" |
| **模型（Model）** | 决策与推理核心 | Codex / Claude / GPT 等 LLM |
| **工具（Tools）** | 让 agent 能行动 | 读写文件、执行命令、搜索、MCP 服务（记忆库、验证服务） |
| **记忆（Memory）** | 对抗上下文窗口限制 | 工作区文件、结构化记忆通道（子目标、失败路径、验证报告） |
| **控制循环（Loop）** | 迭代直到收敛 | 生成 → 验证 → 修复 → 再验证，直到通过或达到迭代上限 |

### 关键认识

- **上下文窗口是最稀缺的资源。** 数学证明可以写到几十页，任何单次对话装不下。agent 必须把中间结论"外置"到记忆系统，每次只取当前所需。这也是 Danus 事实图设计的动机。
- **停止条件必须显式。** "把每个目标定理证出来才停"和"试 10 轮就停"是两种完全不同的系统，成本也完全不同。Danus 的运维文档第一件事就是要求"开始前与主智能体商定停止条件"。
- **自主性是把双刃剑。** agent 可以无人值守跑很久（Rethlas/Danus 都是这个定位），也意味着它犯的错、花的 token 都会累积。第 3 讲会讲怎么用权限分离约束它。

---

## 三、工作流 vs 智能体；Coding Agent 形态

### 工作流（Workflow）≠ 智能体（Agent）

| | 工作流 | 智能体 |
| --- | --- | --- |
| 路径 | **预先编好**：A→B→C 写死在代码里 | **动态决定**：LLM 现场选择下一步 |
| 适用 | 步骤固定、可枚举的任务 | 路径无法预知、需要临场判断的任务 |
| 例子 | "调一次 SageMath 再格式化输出"的脚本 | "自己决定先查文献、再构造反例、再分解子目标"的证明 agent |
| 风险 | 僵化 | 不可预测、需要护栏 |

数学研究任务恰恰是"路径无法预知"的典型——你不知道该先找反例还是先做分解——所以数学智能体通常采用 agent 式而非 workflow 式控制。**但好的 agent 内部会把确定性的子过程固化成脚本/skill**（第 2 讲的主题）。

### Coding Agent：本课程的主角形态

Codex CLI、Claude Code、OpenCode 这类 coding agent 是目前承载数学智能体最普遍的底座，因为它们天然具备：

- **工具集**：读写文件、执行 shell、联网搜索；
- **约定式配置文件**：`AGENTS.md`（跨厂商约定的 agent 说明书）、`CLAUDE.md`、`.agent.md` 等；
- **MCP（Model Context Protocol）**：把外部能力（记忆库、验证服务、arXiv 检索）以标准协议挂进来；
- **Skill 机制**：按需加载的领域知识包（第 2 讲展开）。

Rethlas 和 Danus 都直接建立在 Codex 之上：worker 和 verifier 就是"被规定了角色与工具的 Codex 实例"。

---

## 四、案例解剖：Rethlas 生成智能体

> 课前准备：现场打开 `https://github.com/frenzymath/Rethlas` 的 `agents/generation/AGENTS.md` 对照讲。

Rethlas 是一个自然语言数学推理系统，由**两个** Codex agent 组成：生成 agent 写证明蓝图，验证 agent 检查蓝图并给出结构化裁决。本节只看生成 agent 的"岗位说明书"`AGENTS.md`，观察五要素如何落地。

### 1. 目标（Objective）——写得像合同

```
Given the markdown filepath of a math problem, read that file and produce
a verified markdown proof blueprint at:
- working draft: results/{problem_id}/blueprint.md
- verified proof: results/{problem_id}/blueprint_verified.md
```

注意它明确了：**输入是什么、产物放在哪、什么叫完成**（`blueprint_verified.md` 出现 = 通过验证）。连 `problem_id` 的命名规则（保留 `data/` 下的分类子目录）都写死了。

### 2. 工作区边界（Workspace Boundary）——安全护栏

```
Do not read anything outside this working directory. This is a hard constraint.
```

硬约束写进说明书，防止 agent 翻用户的私人文件。

### 3. 记忆策略（Required Memory Policy）——对抗上下文限制

所有中间推理产物必须持久化到 `memory/{problem_id}/`，并使用 **追加式通道**：

- `immediate_conclusions`（立即可得的结论）
- `toy_examples` / `counterexamples`（玩具例子 / 反例）
- `subgoals`（子目标）
- `failed_paths`（失败路径）
- `verification_reports`（验证报告）
- `branch_states` / `events` ……

这就是"记忆"要素的工程化：不是一句模糊的"记住上下文"，而是**带类型、可检索、只能追加**的结构化记忆。

### 4. 自适应控制循环（Adaptive Control Loop）——agent 式的决策

每个迭代分两步：

- **Step 1 评估状态**：现在主问题是什么？检索够了吗，能不能靠深度推理推进？已有几个分解方案？有哪些新鲜构造/反例？常见失败模式识别出来了吗？
- **Step 2 选下一个 skill**：不预设固定顺序，根据当前证据在 `$obtain-immediate-conclusions`、`$search-math-results`、`$construct-toy-examples`、`$construct-counterexamples`、`$propose-subgoal-decomposition-plans`、`$direct-proving`、`$recursive-proving` 等技能中现场选择。

> 这里埋一个伏笔：**决策逻辑在 agent（AGENTS.md）里，执行方法在 skill（$xxx）里**——这正是第 3 讲要展开的"Agent 与 Skill 的分层"。

### 5. 工具与外部服务

生成 agent 通过 MCP 调用记忆工具（`memory_init` / `memory_append` / `memory_search` / `branch_update`）和**验证服务**——验证 agent 以本地 HTTP 服务（端口 8091）常驻，生成 agent 提交蓝图、收到结构化裁决、修复后再提交，直到产出 `blueprint_verified.md`。runner 脚本 `tests/run_example.sh` 控制最大迭代轮数（`MAX_ITERATIONS`）。

### 小结案例：五要素对照表

| 五要素 | Rethlas 生成 agent 中的实现 |
| --- | --- |
| 目标 | 产出 `blueprint_verified.md` |
| 模型 | Codex |
| 工具 | 文件系统、搜索、MCP 记忆工具、验证 HTTP 服务 |
| 记忆 | `memory/{problem_id}/` 追加式通道 |
| 控制循环 | 自适应评估状态 → 选 skill → 生成→验证→修复，至多 `MAX_ITERATIONS` 轮 |

---

## 五、小结与讨论

### 小结三句话

1. Agent = **LLM 决策核心 + 目标 + 工具 + 记忆 + 控制循环**；它不是更长的 prompt，而是一个能行动、能留痕、能被纠错的系统。
2. 数学任务的路径不可预知，所以数学智能体多用 **agent 式动态编排**，但确定性的子过程会被固化下来（下讲的 skill）。
3. 一份好的 agent 说明书（AGENTS.md）像岗位合同：目标可验收、边界写死、记忆有制度、循环有停止条件。

### 课堂讨论题

- 如果让你设计一个"批改线性代数作业"的 agent，它的五要素分别是什么？停止条件怎么定？

## 课后任务（不计分）

安装任意一个 coding agent（如 Codex CLI），用一句话让它完成一个小任务（例如"写一个脚本验证 $\sum_{k=1}^n k^2$ 的公式并对 $n=100$ 检验"），观察它的 agent loop：它调用了哪些工具？循环了几轮？

## 参考资料

- Rethlas：<https://github.com/frenzymath/Rethlas>（重点读 `agents/generation/AGENTS.md`）
- Danus：<https://github.com/frenzymath/Danus>（重点读 `README.md` 与 `ARCHITECTURE.md`）
