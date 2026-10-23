# 高中数学教师 Agent

一个供支持本地 Skill 的智能体使用的高中数学教师协作项目，覆盖课前备课、例题教学、作业反馈和草稿复盘。**Lesson Materials Builder**（`lesson-materials-builder`）把教案草稿按学生的认知台阶转换为可放映课件；**Math Solver**（`math-solver`）从零求解高中数学题并分步复核；**Math Error Diagnosis**（`math-error-diagnosis`）检查学生提交的解答并定位首错；**Solution Refiner**（`solution-refiner`）只优化已完整诊断为正确的学生解法；**Draft Coach**（`draft-coach`）只分析学生草稿版面，不判断计算对错或识别手写。原有五个技能加上学习任务设计、学习证据汇总、补救教学规划，共八个子技能，由统一的[高中数学教师 Agent](high-school-math-teacher-agent/SKILL.md)按教学周期调度：课前备课 → 例题求解 → 作业诊断 → 正解优化/草稿复盘 → 匿名化补救课件。每项产物分别保留原技能的验证边界；例如，PPT 版面复核不证明数学结论正确。

覆盖函数与导数、三角函数与解三角形、圆锥曲线、数列、向量与立体几何、概率统计，以及集合、逻辑、复数等基础代数内容。


## 一条命令启动工作台

```bash
python3 run.py
```

打开 http://127.0.0.1:8765 。不要双击 `app/static/index.html` 使用工作台：练习保存、模型调用和课件生成需要本地服务；文件预览会显示启动提示。Python 3.10+；学生区的 Web 服务与数据库使用标准库。教师备课区首次使用前，在仓库根目录执行 `pip install -r lesson-materials-builder/requirements.txt`；读取 PDF 教案还需 `pip install pypdf`。真实模型入口使用已安装并登录的 Codex CLI（`codex login status` 可检查登录）。支持 `MATH_CODEX_BIN` 指定 CLI 路径，`MATH_MODEL` 指定模型；不设置时使用用户现有配置。没有模型或登录失败时显示真实错误，不回退到伪造答案。

工作台分为学生练习、教师备课与师生任务三个区域。学生区连接数学求解、过程诊断、正确解法优化和草稿版面反馈，实际执行原有门脚本；结构失败最多反馈修正两次。练习与每次提交保存到 `.local/workbench.sqlite3`，新提交使旧结果成为历史。提示模式保持到用户明确切换；支持历史查看与 JSON 导出。可勾选“用计算工具代回检验候选值”，要求实际执行等式核验；该项需要可选依赖 `pip install -r requirements-verify.txt`，不证明解集完备。教师区将教案整理为逐页大纲，经教师确认后生成可编辑 Markdown 和 PowerPoint，并调用 Builder 脚本独立检查结构与几何；该检查不证明课件数学内容正确或动画可播放。界面采用华东师大官网红色系。

[当前能力与验收](docs/delivery/实施与验收.md) · [架构与运行](docs/delivery/架构与运行.md) · [本轮真实对照实验](evaluation/course-2026-10-22/README.md)

## 把学生与教师串起来

“师生任务”区支持教师填写或起草练习，核对原题后发布；学生领取后进入练习区作答。教师刷新即可看到每题当前提交的诊断与可回查版本，据此生成可编辑补救教案，交给教师备课或布置关联的再练习。学生修订后旧补救草稿会过期，重新规划后才能交接。

新增技能：[`learning-task-designer`](learning-task-designer/SKILL.md)、[`learning-evidence-bridge`](learning-evidence-bridge/SKILL.md)、[`remedial-lesson-planner`](remedial-lesson-planner/SKILL.md)。三者分别负责任务、证据与教学调整，不替代已有求解/诊断技能。工作台模型出题草案未经过自动数学核验，发布前由教师检查；安装 Skill 后可由宿主按任务设计技能调用 Math Solver 核验。

当前支持共用本机数据库的单设备协作演示，不含学生独立账号、跨设备提交或班级管理。工作流、接口与验证边界见 [师生任务交接协议](docs/teaching-loop.md)。

## 单独安装技能

将整个 `math-error-diagnosis/` 目录复制到宿主的技能目录。Codex 的常用位置为 `~/.codex/skills/`；若设置了自定义技能目录，则使用相应位置。避免覆盖同名技能，先比较已有版本。

需要从零求解时安装 `math-solver/`；需要在正确解法上继续优化时同时安装 `math-error-diagnosis/` 和 `solution-refiner/`。完整教师流程可安装 [高中数学教师 Agent Skill](high-school-math-teacher-agent/SKILL.md) 及其引用的八个子技能，仓库根目录 [AGENTS.md](AGENTS.md) 是项目级调度入口；学生练习反馈与教师备课均可在本地工作台使用。单个技能仍可按其边界独立工作。

### 课前教案转课件

`lesson-materials-builder/` 根据初高中 `.docx` / `.pdf` / `.md` / `.txt` 教案草稿生成可编辑的 `课件.md` 和 `.pptx`。工作台教师区实现了“材料整理—大纲确认—源码编辑—渲染复核”流程；也可按 [技能说明](lesson-materials-builder/README.md) 和 [Skill 流程](lesson-materials-builder/SKILL.md) 独立运行。此技能来自上游分支 `feat/lesson-materials-builder`（提交 `6aae555278ed36a34cdf15c2cdc512e9e3725077`），并由项目级教师 Agent 纳入教学周期调度。

```text
请使用 $math-error-diagnosis 检查我的解题过程，指出首个实质错误并给出最小修改。

题目：在 0≤x<2π 内解 sin(2x)=sin(x)。
我的过程：用二倍角公式后，两边除以 sin(x)，得 cos(x)=1/2，
所以解只有 π/3 和 5π/3。
```

也可以向能读取本地文件的 Agent 指定 `math-error-diagnosis/SKILL.md`，要求按其规则检查题目和学生解答。Skill 需要宿主模型执行，Python 脚本不提供通用诊断服务。

只有题目、没有学生解答时，用 `$math-solver` 从零求解：

```text
请使用 $math-solver 求解下面这道题，给出分步推导和核验。

题目：解方程 √(x+2)=x。
```

它产出的是**助手解答**，不是学生的原解答。已有学生解答、需要判断对错时走 `$math-error-diagnosis`；不要用求解结果替换或冒充学生的过程。

学生交的是**草稿纸**（不是作业本上的正式解答）时用 `$draft-coach`：它只看版面习惯，不判断对错。

```text
请使用 $draft-coach 看看我的草稿习惯。

草稿：左上角写 x^3-3x 求极值；中间写 f'(x)=3x^2-3；下面写 3x^2=3 → x^2=1 → x=1（划掉）x=±1；
右边写 f(1)=-2；右下角写 f(-1)=2；底部写 极大值2 极小值-2
```

两条使用要点：**习惯分析不需要原题**；**手写草稿要由你自己把纸上的内容打成文字、或说出版面布局给它**，它不读字符。卡片里的 `scope` 会写明这次只看了版面、没核对题意。

要判断对错、找错因，请走 `$math-error-diagnosis`，不要用本技能。`triage` 出口已移除。

如果发的是**一整张草稿纸**、只想问「我大概做了几道题」，走 `partition` 出口：

```text
请使用 $draft-coach 看一下这张草稿纸，大概做了几道题？
```

它只按版面分块（留白、分隔线、栏位、区域大小），给一个估计范围，并把分不准的地方写出来请你确认。**块数不等于题目数**：一块可能是一道题的一问、一次换方法的尝试或废弃草稿；它不会读纸上的字符。

草稿版面与数学检查按用户意图区分：只问布局习惯时走草稿技能；要求判对错、找错因时走诊断，草稿文本保留为学生原过程。**已判错的选择/填空题**直接走诊断；只有答案时不推断过程。

默认模式是过程检查。可要求“完整纠正”“只给一个提示，别告诉答案”或“仅核对答案”；只有最终答案时不会推断未提供的过程。默认使用高中方法，不擅自扣分，参考答案也需核验。

## 文件结构

```text
math-error-diagnosis/
  SKILL.md                 技能入口、触发描述与审查流程
  agents/openai.yaml       界面信息与默认调用提示
  references/              六份题型清单、判断尺度与示例
math-solver/
  SKILL.md                 求解入口、工作流、数学安全规则与输出契约
  scripts/validate_output.py  结构化输出的结构门（仅标准库）
  references/              输出 Schema 与按题型核验清单
  example/                 完整求解、条件不足示例与可行性测试夹具
  bench/                   51 条案例的确定性评分、oracle/bad 夹具与测试
  tests/                   结构门回归测试（20 项）
draft-coach/
  SKILL.md                 草稿习惯入口（行为契约与 Workflow）
  references/              六维版面尺度、输出 Schema、示例说明、图片入口、题目分区
  scripts/                 三道门：validate_output.py（结构 + hint）、audit_output.py（审计 + refuse）与 partition_check.py（分区），共用 _rules.py
  assets/                  空白卡片骨架 output_template.json 与分块单骨架 partition_template.json
  tests/                   技能自带门测试（38 项）
  bench/                   当前技能版面习惯基准（24 条正面能力案例 + 确定性评分 + 夹具）
  evals/                   旧版「查错」基准，已冻结（见 evals/FROZEN.md）
  example/                 习惯卡、反例卡、整页分块单与三份 refuse 输出
lesson-materials-builder/
  SKILL.md                 教案转课件的触发、六步工作流和质量边界
  scripts/                 PPT 渲染、独立几何复核、配图、回归与隐私扫描
  references/              课件语法、版式规则和配图规范
  evals/                   回归夹具、评估语料和评估方法
high-school-math-teacher-agent/
  SKILL.md                 五项技能的总调度、教学周期工作流和交接边界
docs/                      诊断案例、验证范围与说明
tests/                     草稿门层报告测试与固定案例计算脚本
AGENTS.md                  五个技能的调用与反馈规则
```

优先阅读 [教师 Agent Skill](high-school-math-teacher-agent/SKILL.md)、[技能入口](math-error-diagnosis/SKILL.md)、[代表案例](docs/代表案例.md) 和 [验证说明](docs/验证说明.md)。展示名称与目录名保持一致；统一教师 Agent 通过 `$high-school-math-teacher-agent` 调度八个子技能。

## 复现计算核验

Python 3，三个脚本仅依赖标准库，在仓库根目录执行：

```bash
python3 tests/核验测试数学.py
python3 tests/新例计算核验.py
python3 tests/高中题型计算核验.py
```

它们分别核验10、6、11组固定数学事实。后两个脚本会在同目录生成JSON证据文件，首个脚本将JSON结果输出到终端；生成结果不纳入版本控制。有限样本与浮点容差检查的限制在输出中说明。这些脚本不是模型行为测试，也不代替一般性数学证明。

math-solver 的结构门测试在技能目录内：

```bash
python3 -m unittest discover -s math-solver/tests -p 'test_*.py'
```

当前 20 项，覆盖两份示例、字段缺失与多余、状态冲突、检查状态、步骤序号告警、`--strict` 行为与三类输入非法。结构门只查形状与状态一致性，**不验数学**。根目录 `tests/` 保留草稿门层报告测试与固定案例计算脚本。

草稿技能的门测试在技能目录内：`draft-coach/tests/`（38 项，覆盖版面习惯卡的结构、越界、三个 refuse 出口与分区门），跑 `python3 -m unittest discover -s draft-coach/tests -p 'test_*.py'`；`tests/test_draft_gate_report.py` 覆盖门层报告本身（干净卡与结构损坏卡的退出码、越界反例、多题草稿按块过门的 `audit_draft` 口径、没产卡片记 `none` 并核对标准话术、三类非法输入走退出码 2）。

draft-coach 的两道门可直接复现：

```bash
cd draft-coach
python3 scripts/validate_output.py validate --card example/high_school_cubic.json
python3 scripts/audit_output.py audit --card example/out_of_scope_label.json \
  --draft "左上角写 x^3-3x 求极值；下面写 3x^2=3 → x^2=1 → x=1（划掉）x=±1" --strict
```

第一道应退出 0；第二道结构合格但审计应退出 1——它给学生贴标签（`A_LABEL`），还写了题量计划（`A_PLAN`）。

分区门可直接复现：

```bash
cd draft-coach
python3 scripts/partition_check.py validate --payload example/partition_sheet.json --strict
```

应退出 0。它只查分块单的形状与措辞：块 1–12 个、数量与范围自洽、有不确定说明与确认问题、限制说明齐全，并拦「就是 N 道题」「算错」「我看出来这行写的是…」这类措辞。**它不判断分块是否真的对应题目，也不验证图片。**

草稿评测里每张卡片过不过门，可以只重放退出码、不调用模型：

```bash
python3 tests/behavior-evaluation/draft_gate_report.py tests/behavior-evaluation/draft-coach-2026-10-15
```

它读 `inputs.json` 与 `skill.json`，对保存下来的卡片重跑 `validate` 与 `audit --strict`，记录真实退出码与命中代码，写到 `gates.json`。退出码沿用 0/1/2：0 = 每张卡都过两道门，1 = 有效输入但有卡未过门（或一张卡都没产出），2 = 输入非法。它只说明卡片有没有越过结构线与措辞线，**不说明版面观察是否属实**。

当前项目全量验收（根目录执行）会运行各技能、工作台、数学核验和课件技能的回归探针：

```bash
BENCH_IDENTIFIERS='姓名,学号' python3 scripts/verify_all.py
```

运行前把示例值替换成将要分享的实际标识符；验证摘要只记录配置数量，不记录标识符内容。课件技能把未配置隐私扫描视为未通过。

历史记录：2026-10-10 当时的三个技能通过宿主 skill-creator 的 `quick_validate.py`，当时26项单元测试和27组固定计算通过；该数量不代表当前版本。当前测试范围见 [验证说明](docs/验证说明.md)。另有 [行为对照评测](docs/行为对照评测.md) 保存12题普通问答、Skill回答及匿名独立上下文复核的真实记录；这些小样本结果不构成普遍准确率保证。

**历史记录（旧版查错技能）**：[草稿行为对照评测](docs/草稿行为对照评测.md) 是 2026-10-15 针对旧版 draft-coach 的12条合成草稿对照与门层读数；当前技能已改为只看版面，**这些分数不能用来评价现在的能力**。

旧版「查错」基准在 [draft-coach/evals/](draft-coach/evals/)，**已冻结**：它测的是 2026-10-15 以前以“先查计算错误”为主产品的 draft-coach，不对应当前版面习惯技能。保留它是为了记录当时的案例、锚点校验与门层重放方法；**不要在当前技能上运行**。

当前的版面习惯基准在 [draft-coach/bench/](draft-coach/bench/)：**只评正面能力**，24 条案例覆盖六维分析、短草稿、整页分区与输入形态（图片文字描述、多题分块、初中学段）；越界/拒绝案例已移出默认基准。自动层重放当前三道门并核对 `tool_log`，人工层单独导出。它评的是**已保存的输出**，不调用模型；自动层不验数学，也不验证版面观察是否属实。运行方式见 [bench/README.md](draft-coach/bench/README.md)。

## 能力边界

图片/PDF识别、工具权限、长期记忆和独立验证服务依赖宿主。本项目**不内置任何手写转写（OCR）技能，也不附带学生数据库**；外部 OCR 只能当线索，**不作证据**。

复杂题目仍应审查实际数学依据，不能把有限案例结果视为任意高考题的准确率保证。

math-solver 的“独立核验”是**同一助手换路线复核**，不是第三方独立验证，也不是形式化证明；有限数值检验只覆盖它实际检查的范围。它的结构门只检查 JSON 的形状与状态一致性，不判断数学是否正确。

draft-coach **只看版面习惯，不判断计算对错**。`validate` 只查卡片结构，`audit` 只查越界措辞；两者都**不验证版面观察是否属实**。通过两道门只说明卡片没越过结构线与措辞线，不说明这份习惯分析真的说中了这个学生。

draft-coach 自身只处理**文字还原，或学生自己看照片写下的文字描述**，不做笔迹识别、也不许助手自己看图读字符。学生没给文字时它应当请他打字 / 口述 / 重拍，或只出版面能支撑的习惯卡，而不是猜。手写照片的内容、整张纸上哪块属于哪道题，都没有任何脚本能核，唯一防线是让学生在核对那一步点头。
