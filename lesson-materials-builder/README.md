# lesson-materials-builder

> 把中学教案草稿（`.docx` / `.pdf`）转换成可放映的课堂课件（`.pptx`）的 Claude Code 技能。

**核心主张：按学生的认知台阶切页，不按教案的小节标题。**

---

## 它解决什么问题

教案和课件不是同一份东西。教案写的是「教师怎么想」（教学目标、设计意图、理论依据），
课件要的是「学生看到什么」。

把教案的章节标题直接搬成幻灯片标题，做出来的是**教案的复读机** —— 页数不少，
但每页都在重复同一件事，学生看不出这页要他干什么。

本技能做的是**重新切页**：按学生的**认知台阶**切分，让每页对应一个思维动作
（感受 → 比较 → 抽象 → 应用），而不是对应教案里的一个标题。

> **自检标准：学生扫一眼某页，能不能说出「这页要我干什么」。说不出就是切错了。**

设计取向是 **Markdown 当源，`.pptx` 当交付物**：内容写在 `课件.md` 里，
`build_pptx.py` 渲染成 `.pptx`。要改内容就改 markdown 重新渲染，不必在 PowerPoint 里返工。

---

## 安装

这是一个 [Claude Code](https://claude.com/claude-code) 技能。直接克隆到技能目录：

```bash
git clone <本仓库地址> ~/.claude/skills/lesson-materials-builder
```

Windows（PowerShell）：

```powershell
git clone <本仓库地址> "$env:USERPROFILE\.claude\skills\lesson-materials-builder"
```

装好后重启会话（技能注册表在会话启动时固化），然后用自然语言触发，例如
「把这份教案做成课件」「帮我出这节课的 PPT」并附上教案文件。

### 依赖

```bash
pip install -r requirements.txt
```

核心依赖：`python-pptx`、`matplotlib`、`Pillow`、`numpy`。
可选：`pypdf`（读 `.pdf` 教案）、`fontTools`（字形覆盖检查）、`sympy`（部分三维配图）。

> `.docx` 用标准库的 `zipfile` + 正则直接读 XML，不需要额外依赖。

---

## 用法

技能被触发后，Claude 会按 `SKILL.md` 走完 6 步。手动跑脚本也可以：

```bash
# 1. 出图（配图清单写在 figures.json）
python scripts/make_figures.py figures.json

# 2. 渲染课件
python scripts/build_pptx.py 课件.md -o 课件.pptx

# 3. 独立复核（几何、版式、配图、语体）
python scripts/verify_pptx.py 课件.pptx --figures figures/

# 4. 回归测试（改了这个技能自身之后，秒级、零模型成本）
python scripts/bench.py regress
```

`verify_pptx.py` 是**独立**于渲染器的复核：它不 `import build_pptx`，所以不会
和渲染器犯同一个错（这条独立性由回归测试里的静态断言守住）。

---

## 流程（6 步）

| 步骤 | 做什么 |
|---|---|
| 1. 读教案 | 逐项核对「已有 / 缺失」：课题、年级、教材、课时、教学目标、重难点、**教学过程**、板书、作业 |
| 2. 确认参数 | 年级、课时长度、教材版本、比赛版 / 日常版 —— 缺哪个问哪个，**不猜** |
| 3. 切页 | 按认知台阶切分，**输出大纲请用户确认** |
| 4. 出图 | 配图清单 → `make_figures.py`（matplotlib，纯代码出图，无需外部素材） |
| 5. 渲染 | `课件.md` → `.pptx` |
| 6. 自检 | 逐页确认版式与内容，再跑 `verify_pptx.py` |

第 3 步是整个技能的重心：**这一页到底对应哪个思维动作**。教案的「环节二」里可能
塞着两个不同的思维动作，也可能一个动作被拆在三个环节里 —— 照搬标题就会切错。

---

## `课件.md` 语法

```markdown
---
title: 导数的概念及其意义
version: daily          # 或 contest（比赛版，会校验阐述页是否齐全）
---

# [封面] 导数的概念及其意义
讲师：示例教师
教材：高中数学人教A版选择性必修二

# [标题] 温故知新
- 用二次函数拟合跳水轨迹
!img: figures/diving.png h=4.2
> 研究整体轨迹就足够了吗？

# [重点] 导数的意义
- **几何意义**：瞬时变化率
- **物理意义**：瞬时速度
!!! 数形结合，以直代曲

# [例题] 例题巩固
- 已知圆锥的底面半径为 r，高为 h，求它的体积 V
!ans: 圆柱体积 V = πr²h
!ans: 故 V = 1/3 πr²h
```

- `# [版式] 标题` 起一页，版式省略时默认 `[标题]`
- `!img:` 配图，`!ans:` 单击后显现的答案（先问题、后答案），`!!!` 强调块
- `> ` 驱动问题（只指向下一页）
- 完整语法见 [`references/slides-spec.md`](references/slides-spec.md)，版式规则见
  [`references/deck-rules.md`](references/deck-rules.md)

### 几条硬约束

- 标题 ≤ 12 字；一级要点单页 ≤ 6 行
- 建构段每页都要有图；总结段零图
- 内页（含阐述页）**不出现课题与教材出处** —— 只在封面出现一次
- 正文块留白上限 30pt / 26pt / 行距 1.6（**冻结**，不得为了塞内容而上调）

---

## 回归测试：这个技能怎么防自己变坏

技能里的每个校验器都是「被动」的 —— 只在有人调用时才说话。一条检查哪天被某次
重构悄悄关掉了，从外面完全看不出来：**产出照样生成，告警照样是空的，而空告警和
「检查还在、只是没问题」长得一模一样。**

所以每一组检查都配了一个**规定必须触发它**的夹具（`evals/fixtures/`），哪天检查
哑了，红的是它自己的对照：

```bash
python scripts/bench.py regress          # 36 条断言，13 个探针
```

- **四态**：`PASS` / `FAIL` / `NOT-RUN` / `ERROR`。任一 FAIL / ERROR / NOT-RUN，退出码就是 1。
  「没跑」被算成不通过，是故意的 —— 一个不打招呼就绿的测试台比没有还危险。
- **变异矩阵**：14 个故意做坏的 `.pptx`，每个都必须触发对应那条几何检查。
- **隐私扫描**：`BENCH_IDENTIFIERS=真名,学号 python scripts/bench.py regress`
  扫技能目录本身，防的是真名 / 学号漏进分享包。标识符只从环境变量来，**绝不写进仓库里的任何文件**。

---

## 评估套件（`evals/`）

`evals/` 里还有一层产出层评估：端到端跑一份教案、生成课件，再对产物做断言
（页数、密度、配图、渲染告警、几何缺陷）。

**它的边界写在这里，因为它很重要**：这套断言能量的是「结构对不对」，**量不了
「这份课件好不好」**。要判断「按认知台阶切页」到底有没有价值，需要人来打分 ——
`scripts/blind.py` 提供了一套成对强制选择的盲评工具（位置互换、好看对照、
无法判断率、长度偏置检查），但它只保证「判官稳定」，不保证「判官对」。

设计过程、实测数据和踩过的坑都记在 [`evals/README.md`](evals/README.md) 里，
包括两处**循环论证**是怎么被发现并推翻的。那份文档比结论更有用。

---

## 目录结构

```
SKILL.md                 技能主文件（Claude 读的就是它）
references/              语法规范、版式规则、配图做法
scripts/
  build_pptx.py          课件.md → .pptx
  verify_pptx.py         独立复核（不 import 渲染器）
  make_figures.py        matplotlib 出图
  make_base.py           把你自己的 PPT 做成底版
  bench.py               回归 + 产出层评估
  blind.py               盲评工具
  lint_privacy.py        隐私扫描
assets/base.pptx         默认底版（16:9）
evals/                   回归夹具 + 评估语料 + 方法论记录
```

---

## 已知限制

- **教学理念的原创表述不代笔。** 「逆向设计 + APOS 理论」这类论述需用户自己写；
  写不出来的条目留一个显眼的 `（待填写 …）` 占位符。教学目标 / 重难点 / 解决路径
  能从教案提炼，照写即可。
- 数学公式以**纯文本 + Unicode 符号**呈现（`Δy/Δx`、`lim`），不使用 OMML 公式对象。可编辑性优先。
- 渲染产物的版式可继续在 PowerPoint 里手工微调 —— 脚本只负责把结构立对。
- 学案 / 讲义**不在范围内**。

---

## 隐私

仓库里不含任何真实姓名、学号或教案原文。`evals/corpus/` 下三份语料是自制的，
通用且无隐私。隐私扫描是可重复执行的：`python scripts/lint_privacy.py`。

---

## License

尚未指定。如果你打算把它用在别人也能用的地方，选一个你认可的许可证（MIT / Apache-2.0 / CC BY 4.0 等）再加进来。
