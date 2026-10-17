# 高中数学作业三 Skill 项目

一个供支持本地 Skill 的智能体使用的高中数学作业协作项目。**skill：Math Error Diagnosis**（`math-error-diagnosis`）检查学生实际提交的解答，定位首错并给最小修改；**skill：Solution Refiner**（`solution-refiner`）在当前解答的结论与完整过程都成立、且用户请求优化后，提供三个优化方向；**skill：Draft Coach**（`draft-coach`）只看学生**草稿**的版面习惯（分区与边距、步骤分行与密度、划改与自纠、多路径标记、图形与标注、留白与检验区）——输出六维观察 + 1–3 条习惯 + 下一道题就能执行的动作。**不判断计算对错、不找错因、不做手写转写。** 重点看中学生常见的版面风险（多题混写、高风险步骤挤一行、分类讨论不标号、旧值新值叠在一起、几何图不标关键点、结果旁没有检验区）；草稿允许随意，不评工整。学生发来整张草稿纸时，它还能按**版面**分块，大致估出做了几道题（块数不等于题目数，归属需学生确认）。它不诊断知识漏洞、不贴标签、不给整题重写。

覆盖函数与导数、三角函数与解三角形、圆锥曲线、数列、向量与立体几何、概率统计，以及集合、逻辑、复数等基础代数内容。

## 使用

将整个 `math-error-diagnosis/` 目录复制到宿主的技能目录。Codex 的常用位置为 `~/.codex/skills/`；若设置了自定义技能目录，则使用相应位置。避免覆盖同名技能，先比较已有版本。

需要协作使用时也安装 `solution-refiner/`，并在本项目工作区使用根目录的 [AGENTS.md](AGENTS.md) 作为调度约定。它引用 [交接协议](docs/handoff-protocol.md) 和 `scripts/handoff_check.py`；宿主需实际执行审查与调度，本仓库没有自动运行的后台Agent服务。只使用诊断技能仍可独立检查作业。

```text
请使用 $math-error-diagnosis 检查我的解题过程，指出首个实质错误并给出最小修改。

题目：在 0≤x<2π 内解 sin(2x)=sin(x)。
我的过程：用二倍角公式后，两边除以 sin(x)，得 cos(x)=1/2，
所以解只有 π/3 和 5π/3。
```

也可以向能读取本地文件的 Agent 指定 `math-error-diagnosis/SKILL.md`，要求按其规则检查题目和学生解答。Skill 需要宿主模型执行，Python 脚本不提供通用诊断服务。

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

与 `$math-error-diagnosis` 的分界靠输入，不靠问题：**正式解答**走诊断，**草稿**走这里；**已判错的选择/填空题**先走分诊，确认后再走诊断。

默认模式是过程检查。可要求“完整纠正”“只给一个提示，别告诉答案”或“仅核对答案”；只有最终答案时不会推断未提供的过程。默认使用高中方法，不擅自扣分，参考答案也需核验。

## 文件结构

```text
math-error-diagnosis/
  SKILL.md                 技能入口、触发描述与审查流程
  agents/openai.yaml       界面信息与默认调用提示
  references/              六份题型清单、判断尺度与示例
solution-refiner/
  SKILL.md                 优化卡入口、四字段接口与优化方向表
  solution_card_check.py   优化卡的结构门与越界审计
  example/                 三份示例卡（含混入诊断的反例）
draft-coach/
  SKILL.md                 草稿习惯入口（行为契约与 Workflow）
  references/              六维版面尺度、输出 Schema、示例说明、图片入口、题目分区
  scripts/                 三道门：validate_output.py（结构 + hint）、audit_output.py（审计 + refuse）与 partition_check.py（分区），共用 _rules.py
  assets/                  空白卡片骨架 output_template.json 与分块单骨架 partition_template.json
  tests/                   技能自带门测试（38 项）
  bench/                   当前技能版面习惯基准（24 条正面能力案例 + 确定性评分 + 夹具）
  evals/                   旧版「查错」基准，已冻结（见 evals/FROZEN.md）
  example/                 习惯卡、反例卡、整页分块单与三份 refuse 输出
docs/                      诊断案例、验证范围与说明
tests/                     衔接回归测试、草稿门层报告测试与固定案例计算脚本
scripts/handoff_check.py   交接元信息与当前解答版本检查
AGENTS.md                  三个技能的调用与反馈规则
```

优先阅读 [技能入口](math-error-diagnosis/SKILL.md)、[代表案例](docs/代表案例.md) 和 [验证说明](docs/验证说明.md)。展示名称统一带“skill：”前缀；文件夹名称和 `$math-error-diagnosis`、`$solution-refiner`、`$draft-coach` 调用名保持一致。

## 复现计算核验

Python 3，三个脚本仅依赖标准库，在仓库根目录执行：

```bash
python3 tests/核验测试数学.py
python3 tests/新例计算核验.py
python3 tests/高中题型计算核验.py
```

它们分别核验10、6、11组固定数学事实。后两个脚本会在同目录生成JSON证据文件，首个脚本将JSON结果输出到终端；生成结果不纳入版本控制。有限样本与浮点容差检查的限制在输出中说明。这些脚本不是模型行为测试，也不代替一般性数学证明。

交接与卡片兼容性测试：

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

覆盖过期解答、答案正确但过程无效、论证缺口、只有答案、助手修补稿、提示模式、未请求优化、非法输入及卡片接口。检查状态不放入优化卡。两道卡片门仍不审数学，优化建议需宿主另行核验。草稿技能的门测试在技能目录内：`draft-coach/tests/`（38 项，覆盖版面习惯卡的结构、越界、三个 refuse 出口与分区门），跑 `python3 -m unittest discover -s draft-coach/tests -p 'test_*.py'`；`tests/test_draft_gate_report.py` 覆盖门层报告本身（干净卡与结构损坏卡的退出码、越界反例、多题草稿按块过门的 `audit_draft` 口径、没产卡片记 `none` 并核对标准话术、三类非法输入走退出码 2）。

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

三个技能于2026-10-10通过宿主 skill-creator 的 `quick_validate.py`；全部26项单元测试、27组固定计算、参考链接与界面配置检查通过。新增 [行为对照评测](docs/行为对照评测.md) 保存12题普通问答、Skill回答及匿名独立上下文复核的真实记录；这些小样本结果不构成普遍准确率保证。

**历史记录（旧版查错技能）**：[草稿行为对照评测](docs/草稿行为对照评测.md) 是 2026-10-15 针对旧版 draft-coach 的12条合成草稿对照与门层读数；当前技能已改为只看版面，**这些分数不能用来评价现在的能力**。

旧版「查错」基准在 [draft-coach/evals/](draft-coach/evals/)，**已冻结**：它测的是 2026-10-15 以前以“先查计算错误”为主产品的 draft-coach，不对应当前版面习惯技能。保留它是为了记录当时的案例、锚点校验与门层重放方法；**不要在当前技能上运行**。

当前的版面习惯基准在 [draft-coach/bench/](draft-coach/bench/)：**只评正面能力**，24 条案例覆盖六维分析、短草稿、整页分区与输入形态（图片文字描述、多题分块、初中学段）；越界/拒绝案例已移出默认基准。自动层重放当前三道门并核对 `tool_log`，人工层单独导出。它评的是**已保存的输出**，不调用模型；自动层不验数学，也不验证版面观察是否属实。运行方式见 [bench/README.md](draft-coach/bench/README.md)。

## 能力边界

图片/PDF识别、工具权限、长期记忆和独立验证服务依赖宿主。本项目**不内置任何手写转写（OCR）技能，也不附带学生数据库**；外部 OCR 只能当线索，**不作证据**。

复杂题目仍应审查实际数学依据，不能把有限案例结果视为任意高考题的准确率保证。

draft-coach **只看版面习惯，不判断计算对错**。`validate` 只查卡片结构，`audit` 只查越界措辞；两者都**不验证版面观察是否属实**。通过两道门只说明卡片没越过结构线与措辞线，不说明这份习惯分析真的说中了这个学生。

draft-coach 自身只处理**文字还原，或学生自己看照片写下的文字描述**，不做笔迹识别、也不许助手自己看图读字符。学生没给文字时它应当请他打字 / 口述 / 重拍，或只出版面能支撑的习惯卡，而不是猜。手写照片的内容、整张纸上哪块属于哪道题，都没有任何脚本能核，唯一防线是让学生在核对那一步点头。
