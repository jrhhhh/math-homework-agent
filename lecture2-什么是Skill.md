# 第 2 讲：什么是 Skill（技能）

## 教学目标

1. 理解为什么"通用 agent + 领域知识包"优于"什么都塞进系统提示词"；
2. 掌握一个 Skill 的标准文件结构与各部件作用（`SKILL.md`、frontmatter、scripts、references）；
3. 能逐节读懂一份真实的 SKILL.md（以 sagemath-skill 为范本）；
4. 理清 Skill 与 prompt、tool、MCP 的边界。

## 时间分配

| 环节 | 时间 |
| --- | --- |
| 导入：agent 的"领域无知"问题 | 5 分钟 |
| Skill 的定义与文件解剖 | 15 分钟 |
| Skill 与 prompt / tool / MCP 的关系 | 8 分钟 |
| 案例巡礼：VeryMath AI4Math skill 生态 | 10 分钟 |
| 小结与课堂练习 | 7 分钟 |

---

## 一、导入：agent 的"领域无知"问题

第 1 讲的 agent 有手有脚，但它依然是个"外行"：

- 它不知道 SageMath 里多项式环的正确构造是 `PolynomialRing(QQ, names=("x",))`，会凭记忆瞎编 API；
- 它不知道 OSQP 求解器要求目标写成 $\frac12 x^\top P x + q^\top x$，如果你的原问题是 $x^\top Qx$，**必须令 $P=2Q$**——少这个因子 2，答案全错；
- 它不知道 Lean/mathlib 的工作区怎么搭、`sorry` 为什么不能留在最终交付里。

这些知识有三个共同点：**专业、琐碎、可枚举成流程**。每次开新对话都重讲一遍不现实，全塞进系统提示词又会挤爆上下文、互相干扰。

> **核心矛盾**：通用模型什么都会一点，但每个领域的"行家规矩"它记不牢、也装不下全部。

**Skill 就是解决这个矛盾的发明：把某个领域的行家规矩打包成一个可安装、可发现、按需加载的知识包。**

---

## 二、Skill 的定义与文件解剖

### 定义

> **Skill（技能）**：一个自包含的目录，以 `SKILL.md` 为入口，向 agent 提供完成某类任务所需的**工作流、规则、脚本与参考资料**。agent 在任务匹配时"翻开"它，照章执行。

关键性质：

- **按需加载**：description 匹配当前任务时才进入上下文，不占平时的窗口；
- **可执行**：不只讲大道理，还带脚本（验证器、检索器、环境探针）；
- **有纪律**：明文规定禁止行为与输出标准。

### 标准目录结构（以 sagemath-skill 为实物）

```
sagemath-skill/
├── SKILL.md                  ← 入口：触发条件 + 全部纪律
├── README.md                 ← 给人看的说明
├── skill.json                ← 元数据（可为空）
├── scripts/                  ← 可执行工具
│   ├── sage_ref_search.py        # 全文检索自带参考手册
│   ├── sagemath_runner.py        # macOS/Linux 运行 SageMath 代码
│   └── sagemath_runner_wsl.py    # Windows(WSL) 运行器
└── references/               ← 领域参考资料（不预先加载，检索式取用）
    ├── api/                    # 处理过的 SageMath 全文参考（按域分目录）
    ├── domain_index.md         # 域目录导航
    ├── reference_manifest.jsonl
    └── install_sagemath.md
```

> 现场演示：打开 <https://github.com/VeryMath/AI4Math-Sagemath-skill> 对照目录讲。

### 解剖 `SKILL.md`：五个功能段

**① frontmatter —— 触发器（全篇最重要的几行）**

```yaml
---
name: sagemath-skill
description: Use SageMath as a Python package for exact symbolic and
  mathematical computation ... Use when a task needs SageMath APIs for
  algebra, number theory, combinatorics, polynomial rings, ...
---
```

`description` 不是简介，而是**给 agent 的路由表**：它在告诉 agent"什么任务该翻我"。写得越具体（列出数学分支、任务动词），触发越准。

osqp-solver 的 description 还示范了**负面触发器**：

```yaml
Use when a task names OSQP, osqp Python, operator-splitting QP, convex QP ...
Do not use for mixed-integer, nonconvex quadratic, nonlinear-constraint,
or general conic/SOCP problems.
```

"什么时候**别**用我"和"什么时候用我"同样重要——防止 MILP 任务被误路由到 QP 求解器。

**② 核心规则（Core Rules）——防止最常见翻车**

sagemath-skill 开篇三条铁律：

1. 把 SageMath 当 Python 包用（`from sage.all import *`），不用 REPL preparser 专用语法；
2. **Never invent SageMath APIs from memory**——先查参考，再写代码；
3. 用文档里的 Python 调用约定，显式构造母环/母域，不依赖隐式强制转换。

**③ 工作流（Lookup Workflow）——六步标准动作**

分析数学对象 → 构造英文检索词 → `sage_ref_search.py` 查参考 → 打开命中的 `.txt` 核对构造器/方法签名 → 写代码 → 用对应平台的 runner **执行并验证**。失败则带着错误信息回去再查。

**④ 输出标准（Output Standards）——证据导向**

- 给出可执行 Python 代码而非 Sage 提示符抄本；
- **必须附真实运行输出**；跑不了就明说；
- 把计算结果翻译回数学语言。

**⑤ 禁止行为（Prohibited Behavior）——画红线**

- 不许整吞无关大文件（先检索再精读）；
- 不许无证据跨域（环论问题不许因为名字相近就用微积分 API）；
- **不许把精确计算偷偷降级成纯 Python 近似**；SageMath 不可用就报告并请求安装；
- 不信失败/部分计算，修好重跑，只报最终验证过的结果。

### 小结：一份 SKILL.md 的"最小骨架"

```
frontmatter（name + 精准 description，含负面触发）
+ 适用范围/铁律
+ 分步工作流（每步配可执行命令）
+ 输出与证据标准
+ 禁止行为
+ scripts/（确定性操作脚本化）
+ references/（大部头资料检索式取用，不预载）
```

---

## 三、Skill 与 prompt / tool / MCP 的关系

这四个词经常被混用，必须分清：

| 概念 | 本质 | 类比 | 例子 |
| --- | --- | --- | --- |
| **Prompt** | 一次性的指令文本 | 口头叮嘱 | "请用中文回答" |
| **Tool** | agent 可调用的**函数/动作** | 手 | 读文件、跑 shell、`memory_append` |
| **MCP** | 挂载工具的**标准协议** | 手的接口标准 | Rethlas 的记忆服务、验证 HTTP 服务 |
| **Skill** | 围绕一类任务的**知识与流程包**（可含工具） | 操作手册 + 配套工具箱 | sagemath-skill |

一句话记忆：

> **Prompt 是"叮嘱"，Tool 是"手"，MCP 是"手的接口"，Skill 是"培训手册 + 工具箱"。**

Skill 的独特价值在于**把隐性专家经验显性化、文件化**：老数学家知道"先查手册再写代码""结果必须有运行证据"，skill 把这些规矩写成任何 agent 都能继承的文本。同一个 skill 可以被 Codex、Claude Code、OpenCode 等不同 agent 安装复用——AI4Math-Optimization 的安装说明就是"让 AI 帮你装 skill"的一段话。

---

## 四、案例巡礼：VeryMath AI4Math skill 生态

VeryMath 组织（<https://github.com/orgs/VeryMath/repositories>）维护了一组 AI4Math 技能仓库，正好展示 skill 的三种组织形态：

### 形态一：单技能仓库 —— AI4Math-Sagemath-skill

一个仓库 = 一个 skill，围绕一个工具做深做透：自带全文参考手册 + 检索脚本 + 跨平台运行器 + 安装指南。适合"教 agent 用一个大型工具"。

### 形态二：技能族仓库 —— AI4Math-Optimization

一个仓库装 6 个互相配合的 skill，按**问题类**划分：

| Skill | 负责的数学疆域 |
| --- | --- |
| `optskills` | 103 张运筹优化问题原型卡，自然语言 → 建模 |
| `mixed-integer-programming` | MILP/MIP 建模 |
| `second-order-cone-programming` | SOCP 建模与 cvxpy 流程 |
| `osqp-solver` | 连续凸 QP 的 OSQP 求解、状态门、独立验证 |
| `cdopt-optimization` | 流形约束优化（CDOpt） |
| `or-solver` | 指定求解器的依赖、license、环境排障 |

设计要点：**每个 skill 疆域清晰、互不重叠，负面触发器防止越界**；`or-solver` 只配环境不做建模——职责单一。

### 形态三：技能 + 共享运行时层 —— AI4Math-Lean-Agents

```
skills/
├── lean-setup/          ← 用户入口：装 Lean4/elan/lake/mathlib 工作区
├── lean-formalization/  ← 用户入口：命题形式化、修证明、补 sorry
└── lean-runtime/        ← 共享支持层：脚本、schema、prompt、测试
```

两个面向用户的 skill 共享一个**不直接对外**的 `lean-runtime` 支持层（脚本、校验器、后端适配清单）。还附了完整交互样例 `examples/lean-setup-add-zero.md`——**用样例教 agent 比用抽象规则更稳**。

### 生态其余成员（一句话各扫一眼）

- **AI4Math-Paper-Reading**：结构化读论文、定理依赖分析、"论文→skill"萃取（skill 还能生产 skill！）
- **AI4Math-Writing**：有出处的数学写作、证明义务审查、投稿级 LaTeX 流程
- **AI4Math-Auto-Research**：自动研究流程、问题发现、证明蓝图评审
- **AI4Math-Computational-Mathematics**：计算数学、不变量计算、科学代码复现
- **AI4Math-Evolving**：OpenEvolve 式程序演化实验
- **AI4Math-MathTool**：独立数学工具与 coding-agent 适配器

---

## 五、小结与课堂练习

### 小结三句话

1. Skill = **可安装、可发现、按需加载的领域知识包**：`SKILL.md`（触发条件 + 纪律 + 工作流）+ scripts + references。
2. 写好一个 skill 的要点：**description 精准（含负面触发）、确定性操作脚本化、输出必须带证据、禁止行为画红线**。
3. Skill 让专家经验脱离具体模型自由流通——这是 AI4Math 生态正在做的事。

### 课堂练习

为下面这个假想 skill 写 frontmatter 的 `description`（含一句负面触发）：

> 一个"LaTeX 论文投稿前检查"skill：检查宏包冲突、未定义引用、overfull box、参考文献格式。

（提示：模仿 osqp-solver 的 "Use when ... Do not use for ..." 句式。请 2 组展示，点评"触发词是否具体、负面边界是否清晰"。）

## 课后任务

想一个你日常数学工作里反复做的机械流程（例如：检查作业答案的量纲、验证一个恒等式、批量生成练习题），列出它的标准动作清单——第 4 讲我们将把它做成真正的 skill。

## 参考资料

- sagemath-skill 全文：<https://github.com/VeryMath/AI4Math-Sagemath-skill/blob/main/sagemath-skill/SKILL.md>
- osqp-solver（负面触发器范本）：<https://github.com/VeryMath/AI4Math-Optimization/blob/main/skills/osqp-solver/SKILL.md>
- AI4Math-Lean-Agents（共享 runtime 层范本）：<https://github.com/VeryMath/AI4Math-Lean-Agents>
