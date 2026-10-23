# 高中数学教师 Agent 调度约定

本文件是项目根目录的 Agent 入口（AGENTS.md）；完整可安装调度技能见 [high-school-math-teacher-agent/SKILL.md](high-school-math-teacher-agent/SKILL.md)。项目覆盖课前备课与课件、课堂例题求解、作业诊断、正确解法优化和草稿复盘。默认使用中文和高中方法，尊重教材版本与反馈模式。

## 技能与职责

- skill：**Math Solver**（`math-solver/SKILL.md`）：从零求解高中数学题——解析题意、选择高中范围内的方法、分步推导并独立核验，输出可核验的解答与下游教学备注。产出的是**助手解答**，不是学生解答；不检查、不修补、不优化学生已经写出的解答，也不做图片或手写转写。
- skill：**Math Error Diagnosis**（`math-error-diagnosis/SKILL.md`）：检查题目、答案和解答过程，定位首错，给最小修改；处理信息不足、论证缺口与答案正确但过程有误。
- skill：**Draft Coach**（`draft-coach/SKILL.md`）：只看学生**草稿**的版面习惯——分区与边距、步骤分行与密度、划改与自纠、多路径标记、图形与标注、留白与检验区——输出六维观察 + 1–3 条习惯 + 下一道题可执行的动作。重点看中学生常见的版面风险（多题混写、高风险步骤挤一行、分类讨论不标号、旧值新值叠在一起、几何图不标关键点、结果旁没有检验区）；**草稿允许随意，不评工整**。**不判断计算对错、不找错因、不给最小修改。** 不诊断知识漏洞、不贴标签、不给整题重写、不出变式题、不排复习计划。学生发来整张草稿纸、问「大概做了几道题」时，走 `partition` 出口：只按版面分块，给估计数与范围；**块数不等于题目数**，归属需学生确认。
- skill：**Solution Refiner**（`solution-refiner/SKILL.md`）：仅在数学诊断先确认当前学生原文结论正确、过程完整且用户明确要求优化后，输出三个有依据的解法优化方向；结构与措辞分别通过技能脚本门。门不证明数学正确或优化建议有效。
- skill：**Lesson Materials Builder**（`lesson-materials-builder/SKILL.md`）：把初高中教案草稿转为按认知台阶组织的可放映 `.pptx`，同时保留可编辑 Markdown 源；生成前先核对教学参数并让用户确认大纲。它不检查学生作业，也不证明课件数学内容正确。

项目级调度顺序：教案/备课课件 → Lesson Materials Builder；只有题目且要求求解 → Math Solver；包含学生正式解答 → Math Error Diagnosis；明确优化且完整诊断通过 → Solution Refiner；仅分析草稿版面 → Draft Coach。课后补救课先从诊断中提炼匿名化教学目标，再由教师提供教案草稿交给 Lesson Materials Builder。跨技能工作流、输入和验证边界见 [教师 Agent Skill](high-school-math-teacher-agent/SKILL.md)。

未包含 presolve-starter；不会开始时可给起步帮助，但不要声称调用未安装技能。本项目**不内置任何手写转写（OCR）技能**：把草稿照片变成文字不归这套技能管，也不许由助手自己看图代劳——原因见 [draft-coach/references/image-intake.md](draft-coach/references/image-intake.md) 第一条。外部 OCR 若由宿主提供，只能当版面/内容的线索，**不作证据**；学生确认之前，它不进入任何结论。

## 调度

1. **先看输入。** 只有题目、没有学生解答，且用户要求求解、证明、求范围或完整解答 → 调用 math-solver。
2. 输入里有学生**已写出的正式解答** → 先调用 math-error-diagnosis。math-solver 不替代诊断；也不得把助手解答当作学生原解答提交检查或评价。输入带学生解答时保留原文，不要用求解结果悄悄替换它。
3. 解答有错或论证缺口：给诊断/修补或提示，等待学生修订并重新检查。助手修补稿不冒充学生解答。
4. 用户只要求检查时完成检查即可。用户要求提示时持续一次一个提示，不因自动调度泄露解答。
5. 用户要求优化时先调用 Math Error Diagnosis 检查这份提交；只有它判定正确且无首错时才调用 Solution Refiner。错误、缺步骤、答案单独出现、来源不是学生、提示模式或检查不完整时均不得进入优化。
6. 学生改变题目、参数、过程或提交新方法后旧检查失效，重新调用诊断；不能把旧解答的正确性状态转给新解答，也不能把 math-solver 的答案当作学生的过程状态。

问题有多个小问时按题号绑定各自题目、过程与状态，检查依赖，不用某一小问通过替代整套作业核验。math-solver 求解多小问时同样逐问给状态，不因一问通过就声称整题完成。

math-solver 的机读输出写好后，在 `math-solver/` 目录运行 `python3 scripts/validate_output.py validate --card output.json --strict`：退出 **0** 才可交付，**1** 结构或状态一致性不合格，**2** 输入非法。结构门只查形状与一致性，**不验数学**。

## draft-coach 的选用条件

draft-coach **不参与求解或诊断链路**，也不消费交接包。它**只看草稿的版面习惯，不判断计算对错，也不做手写转写**。

**分界线结合用户意图与输入：**

- 学生交的是**作业本 / 答卷上的正式解答** → `math-error-diagnosis`：首错定位、最小修改、分层提示，有六份题型清单。
- 学生交的是**草稿纸**且只问版面习惯 → `draft-coach`：六维版面习惯（分区与边距、步骤分行与密度、划改与自纠、多路径标记、图形与标注、留白与检验区）。
- 学生交的是**整张草稿纸**、问「大概做了几道题」 → draft-coach 的 `partition` 出口：只按版面分块，给估计数与范围；不读字符、不查错、不产六维卡，归属由学生确认。
- 学生交的是**已判错的选择/填空题** → 直接走 `math-error-diagnosis`。本技能**没有 `triage` 出口**；只有答案时只能核验答案，不能推断过程。

**两者不可互相替代**：draft-coach 没有题型清单，不做首错定位和分层提示；math-error-diagnosis 不做版面习惯分析。

若草稿中有学生过程且用户要求判对错或找错因，保留原文并交给 `math-error-diagnosis`；不能因为材料名叫“草稿”而拒绝数学检查。

其余边界：

- 用 draft-coach：学生**提供了草稿**（文字还原，或他自己对一张手写照片的文字描述），并问草稿组织、分行、涂改、多路径、画图、留白；**不用于**没有草稿时（只给题目、只给最终答案或只有答卷），**不用于**已成立解答的优化（交由 Math Error Diagnosis 完整核验后再进入 Solution Refiner）。
  **不判断对错、不诊断知识漏洞、不贴标签、不给整题重写、不出变式题、不排复习计划、不评分扣分**。
- **缺原题时习惯分析不降级**：只做版面观察，`scope` 写明"未核对题意"；不得含糊成"检查过了"。
- draft-coach 的卡片过两道门，**分处两个脚本**：`scripts/validate_output.py validate`（结构）与 `scripts/audit_output.py audit`（越界措辞）。
  两者共用常量模块 `scripts/_rules.py`；判据冲突时以脚本常量为准。
  退出码：**0** 通过 / 干净 · **1** 有效但不合格 · **2** 非法输入。
  **两道门都不验数学，也不验证版面观察是否属实**；宿主必须人工复核。
- `partition` 出口另过 `scripts/partition_check.py validate`：查块 1–12 个、数量与范围自洽、有不确定说明与确认问题、限制说明齐全，并拦「就是 N 道题」「算错」「我看出来这行写的是…」这类措辞。它**不判断分块是否真的对应题目，也不验证图片**。退出码沿用 0/1/2。
- `refuse` 的退出码另有一套读法：**2 = 草稿本身不能当证据**（没给 / 给了但用不了）；
  **1 = 草稿没问题，但这个问题不归本技能管**（比如要判对错、变式题或复习计划）。判断理由是模型给的，脚本认不出来。

## 维护与验证

修改接口后运行 `python3 -m unittest discover -s tests -p 'test_*.py'`；math-solver 的结构门测试在技能目录内，另跑 `python3 -m unittest discover -s math-solver/tests -p 'test_*.py'`（20 项）；draft-coach 自己的门测试在技能目录内，另跑 `python3 -m unittest discover -s draft-coach/tests -p 'test_*.py'`（38 项）。Lesson Materials Builder 的确定性回归在 `lesson-materials-builder/` 内运行 `python3 scripts/bench.py regress`，产出还须按该技能要求用 `verify_pptx.py` 复核。Solution Refiner 的交接协议测试在根目录 `tests/test_handoff.py`。版面习惯基准在 `draft-coach/bench/`，另有 44 项测试与 `schema_check.py`；改案例或门后必须重跑真实输出（`tools/build_dataset.py` → `schema_check.py` → oracle/bad 夹具 → `evaluate.py`），不能凭印象写“应该会通过”。分区门用 `draft-coach/example/partition_sheet.json` 复现：在技能目录跑 `python3 scripts/partition_check.py validate --payload example/partition_sheet.json --strict`，应退出 0。数学参考资料变化时运行相关固定计算脚本。保留五个技能（math-solver / math-error-diagnosis / solution-refiner / draft-coach / lesson-materials-builder）的职责边界和各自输出契约；math-solver 输出 schema 的结构核验、同一助手复核和独立验证要分别陈述。单独使用 Skill 时由宿主调度；`app/` 工作台覆盖学生练习反馈链、教师备课和师生任务交接；备课区实际调用 lesson-materials-builder 的本地脚本。实际数学审查、结构门与课件复核分别陈述。

`draft-coach/evals/` 是旧版「查错」基准，已冻结（见 `draft-coach/evals/FROZEN.md`），不要在当前技能上运行；当前的版面习惯基准在 `draft-coach/bench/`，评的是已保存输出，不调用模型。

改任何门脚本或卡片 schema 后，必须重跑真实输出，不许凭印象写"应该会通过"。同伴仓库的副本只供比对，不是交付物；**不去修改同伴仓库的任何文件**。

**Windows 注意**：`PATH` 里的 `python` / `python3` 可能是应用商店的占位程序，会静默失败、什么都不输出。本机可用的解释器为 `"D:/Program Files/anaconda3/python.exe"`。技能内测试用 `sys.executable`，可直接运行。


## 本地工作台

`python3 run.py` 启动回环地址上的本地 Web 服务。`app/core.py` 处理路由、输出包装和真实门反馈，`app/server.py` 保存不可变提交版本；`app/model.py` 在新上下文中调用已登录的 Codex CLI。不得用夹具冒充运行结果。

工作台的 `refine` 模式会先执行 Math Error Diagnosis。只有当前学生原文通过诊断并判为正确，才交由 Solution Refiner；优化卡再经过该技能的结构门和严格措辞审计。修改题目、学段或解答会生成新版本并重新诊断。

修改工作台后运行 `python3 -m unittest discover -s app/tests`；全量常规验收运行 `python3 scripts/verify_all.py`。`evaluation/course-2026-10-22/runs/initial/frozen_source/` 是已评测代码快照，只用于复现，不作为工作台当前源码编辑。真实实验报告必须标注所用快照，不能把后来机制改动的效果归给先前实验。

提示模式不能通过附加字段、运行记录或导出泄露完整解答。结构门对提示字段的检查不代表完整语义检查已经通过；真实行为由评测与人工复核另行判断。历史结果只能代表它绑定的原提交版本。


## 师生任务衔接

新增三个技能与原有五个技能共同构成八技能教学周期：

- **Learning Task Designer**（`learning-task-designer/SKILL.md`）：教师目标/教材材料 → 练习草案 → 教师核对后发布固定原题；新题需要 Math Solver 核验，工作台模型草案标注未核验。
- **Learning Evidence Bridge**（`learning-evidence-bridge/SKILL.md`）：读取任务项绑定的当前学生提交，按目标汇总诊断状态与证据版本；不重新判题，不将未提交/失败/提示/仅答案当作完整过程诊断。
- **Remedial Lesson Planner**（`remedial-lesson-planner/SKILL.md`）：当前诊断证据 → 可编辑补救教案 → Lesson Materials Builder 或关联再练习。引用实际提交 ID；版本变化时旧计划失效。

工作台“师生任务”由 `app/teaching_loop.py` 处理，复用原有练习的不可变提交与诊断。任务原题固定，任务项绑定练习会话，学生修改题目/来源/学段使绑定失效；再次领取会新建原题会话并保留旧记录。共用本机数据库，尚未提供独立账号或跨设备班级访问。协议见 `docs/teaching-loop.md`。新增行为测试在 `app/tests/test_teaching_loop.py`，与工作台 HTTP 测试一起运行。保留冻结实验源码和本地 RSI 资料。
