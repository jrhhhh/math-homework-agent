# error-atlas · 错题病理归因与个性化出题（课堂作品）

《数学智能体工程与实践》第 4 讲动手作品第三件——`my_skill/`（presolve-starter）与
`solution_refiner/`（solution-refiner）的姊妹篇，接在同伴的 `math-error-diagnosis` **下游**。

**学生攒了一摞已经修好的错题，每道都有同伴给出的错因结论。** 本技能做两件事：

1. **错题归因整理**：横向聚合，找出**跨题共享的错误模式**，给出一张错题病理图
   ——3 条模式 + 跨题共同点 + 仍成立的优势 + 一个**待验证**的能力训练目标；
2. **举一反三·个性化出题**（**仅当学生明确要求**）：按这些模式定制 **5 道练习**，
   每题绑定它治哪个模式，覆盖三档难度。

四件作品在同一个闭环上的位置：

```
不会开始 → presolve-starter                （事前：启动）
做错了   → 同伴 math-error-diagnosis       （事后：从错到对）
        → 攒够 ≥2 道 → error-atlas 第一段   （跨题：从病例到模式）      ★本技能
        → 学生要求出题 → error-atlas 第二段 （定制：从模式到练习）      ★本技能
做对了   → solution-refiner                （事后：从对到好）
```

本技能是四件里**唯一有两份产物、三道门、且唯一消费同伴输出**的那个。

## 结构

```
error-atlas/
├── SKILL.md                  ← 入口（触发条件 + 三条上游接口 + 纪律 + 两段式工作流 + 红线）
├── README.md                 ← 给人看的说明（本文件）
├── DESIGN.md                 ← 设计稿：分工表 + 卡片 schema + 52 条判据逐条清单
├── CONFLICTS.md              ← 与上游 math-homework-agent 的冲突核查（含原文行号）
├── error_card_check.py       ← 确定性操作脚本（纯标准库，无依赖，四个子命令）
├── verify_all_gates.py       ← 判据覆盖核验：证明 52 个码每一个都能被真实触发
├── real_output.txt           ← 下面所有"真实输出"的完整原始记录（可复现）
└── example/
    ├── DEMO.md                 ← ★完整走一遍：六道错题 → 病理图 → 定制练习（含真实输出与两版题纸）
    ├── cases_junior.json       ← 6 道错题 + 每道的同伴错因结论
    ├── cases_junior_thin.json  ← 教具：把 1 道题的核验方式降级成 numeric_only
    ├── junior_three_cases.json ← 正常卡（未授权出题，practice_items 为空）
    ├── practice_with_answers.json ← 出题版（5 题三档，每题绑定一个模式）
    ├── bad_card.json           ← 教具一：结构合法但**越界**（audit 驳回 8 条）
    ├── bad_thin_card.json      ← 教具二：结构合法但**证据不足**（证据门驳回 4 条）
    ├── bad_practice_card.json  ← 教具三：归因合格但**出题不合格**（出题门驳回 3 条）
    └── build_cards.py          ← 生成器：按真实内容算指纹，示例卡可复现
```

## 三道门

| 门 | 命令 | 查什么 | 不查什么 |
| --- | --- | --- | --- |
| 结构门 | `validate` | 八个顶层字段、恰好 3 条模式、**两份词表**白名单、`case_count ≥ 2`、证据格式含指纹、画像聚焦与限定词 | 证据是否属实、模式是否真的共享 |
| 证据 · 引文 · 越界门 | `audit --cases` | 跨题证据（题号 / 内容指纹 / 原文支持 / 样本量 / 同伴结论状态）、引文合法性（自产错因 / 否定同伴 / 稳定判定 / 单题诊断）、是否跑到别人地盘 | 数学是否正确 |
| 出题门 · 答案核验门 | `practice` | 授权标记、每题绑定模式、三模式全覆盖、三档难度、去重、答案不泄漏、**一小类题精确有理数代回** | 题目质量、难度标注是否名副其实 |

## 快速体验（以下全是本机真实输出）

```bash
# 0) 两份菜单：聚合维度表（学生维度）+ 同伴六类（题目维度）
python3 error_card_check.py patterns --problem "已知二次函数 f(x)=x^2-4x+3，求它与 x 轴交点的个数。"

# 1) 结构门：0 = 通过，1 = 结构不合格，2 = 输入非法
python3 error_card_check.py validate --card example/junior_three_cases.json

# 2) 证据·引文·越界门（必须带 --cases）
python3 error_card_check.py audit --card example/junior_three_cases.json --cases example/cases_junior.json

# 3) 出题门 + 答案核验门
python3 error_card_check.py practice --card example/practice_with_answers.json --verify-answers

# 4) 52 条判据的覆盖核验
python3 verify_all_gates.py
```

### 正常卡：三道门全过

```
$ python3 error_card_check.py validate --card example/junior_three_cases.json
{ "action": "validate",
  "input": { "card": "example\\junior_three_cases.json" },
  "method": "字段完整性 + 恰好 3 条模式 + 双词表白名单 + case_count 样本量 + 证据格式（含内容指纹）+ 画像聚焦与限定词",
  "errors": [], "warnings": [], "passed": true,
  "capability_note": "结构门不是数学判断：card 字段齐、样本量达标，不等于归因成立。" }
exit=0

$ python3 error_card_check.py audit --card example/junior_three_cases.json --cases example/cases_junior.json
{ "action": "audit",
  "method": "证据门（题号/内容指纹/原文支持/样本量/同伴结论状态）+ 引文门（自产错因/否定同伴/稳定判定/单题诊断）+ 越界门",
  "cases_seen": ["T1", "T2", "T3", "T4", "T5", "T6"],
  "cases_touched": ["T2", "T3", "T4"],
  "errors": [], "warnings": [], "passed": true,
  "capability_note": "证据门是关键词匹配且忽略个位数字；case_count 与 cause.method 都是声明值，脚本查不出声明是否为真。" }
exit=0

$ python3 error_card_check.py practice --card example/junior_three_cases.json
{ "action": "practice",
  "method": "授权门 + 绑定门（pattern_ref / 样本量 / 覆盖 / 难度三档 / 去重）",
  "referable_patterns": { "1": "条件加工缺位", "2": "分支穷尽不足", "3": "过程规范松动" },
  "errors": [],
  "warnings": [ { "code": "W_NO_GENERATION_BASIS", "basis": "",
                  "detail": "出题依据应点名至少一个聚合维度与至少两个题号" } ],
  "passed": true,
  "capability_note": "…" }
exit=0
```

`W_NO_GENERATION_BASIS` 是**故意留着的**：这张卡没有出题，`generation_basis` 为空字符串，
告警提醒"想出题就得写清依据"。它不拦截交付（exit=0），加 `--strict` 才会。

### 出题版：答案核验门真的算了一次

```
$ python3 error_card_check.py practice --card example/practice_with_answers.json --verify-answers
{ "action": "practice",
  "method": "授权门 + 绑定门（pattern_ref / 样本量 / 覆盖 / 难度三档 / 去重）+ 答案核验门（精确有理数代回）",
  "errors": [],
  "warnings": [
    { "code": "W_NO_SOLUTION_BASIS", "id": "P4", "status": "skipped",
      "reason": "题干不是可解析的一元/二元一次方程（组）",
      "detail": "超出可判定范围，明确跳过——不假装验过" },
    { "code": "W_NO_SOLUTION_BASIS", "id": "P5", … } ],
  "passed": true,
  "answer_verification": {
    "checked": [
      { "id": "P1", "status": "verified", "solved": { "x": "2" },
        "note": "精确有理数代回成立（工具辅助核验，非独立验证）" },
      { "id": "P2", "status": "verified", "solved": { "x": "2" }, … },
      { "id": "P3", "status": "verified", "solved": { "x": "2" }, … } ],
    "problems": [],
    "skipped": [ { "id": "P4", "reason": "题干不是可解析的一元/二元一次方程（组）", "status": "skipped" },
                 { "id": "P5", … } ] } }
exit=0
```

**请特别注意这里的分寸**：P1–P3 是"用 `fractions.Fraction` 精确代回验过"，
P4–P5 **明确 skipped 且给出原因**——二次函数与直线交点问题超出可判定范围，
脚本**不假装验过**。这正是同伴"先核验题目条件、解和完整性"那条要求的落地方式：
能算的真算，算不了的明说。

### 三份教具：每份各演示一道**互相独立**的门

**教具一 · `bad_card.json`——结构合法但越界。** `validate` 放行，`audit` 驳回：

```
$ python3 error_card_check.py validate --card example/bad_card.json
{ "errors": [], "warnings": [], "passed": true }        exit=0

$ python3 error_card_check.py audit --card example/bad_card.json --cases example/cases_junior.json
{ "errors": [
    { "code": "E_CASE_COUNT_MISMATCH", "index": 1, "case_count": 2, "cited": ["T4"] },
    { "code": "A_NEW_CAUSE", "field": "error_patterns[1].countermeasure",
      "text": "你之所以错是因为审题太快，根本原因是习惯问题；每天做 5 道，一周就能补上。" },
    { "code": "A_PLAN",   "field": "error_patterns[1].countermeasure", … },
    { "code": "A_OVERRIDE","field": "error_patterns[2].countermeasure",
      "text": "其实不是分类问题，你就是不会分情形，得分一直上不去，置信度不高。" },
    { "code": "A_STABLE_JUDGMENT", … }, { "code": "A_SCORE", … },
    { "code": "A_CONFIDENCE", … },
    { "code": "A_VARIANT", "field": "error_patterns[3].countermeasure",
      "text": "你太粗心了。下面这道题你试试：解 3x-1=5。",
      "detail": "归因字段里夹带题目：练习只能放进 practice_items" },
    { "code": "A_STABLE_JUDGMENT", "field": "capability_profile",
      "text": "你长期能力不足：步骤留痕与记录一直很弱，初步判断已可确认。" } ],
  "warnings": [ { "code": "W_LANGUAGE", … "detail": "语气对人不对事" } ],
  "passed": false }
exit=1
```

**8 条 error 一次报全**，覆盖四类越界：自产错因、否定同伴结论、把题目夹带进归因字段、
以及最要紧的 `A_STABLE_JUDGMENT`——**"一直很弱"正是同伴明令禁止的稳定能力判定**。

**教具二 · `bad_thin_card.json`——结构合法但证据不足。** 它一条越界措辞都没有，
却被证据门驳回：

```
$ python3 error_card_check.py validate --card example/bad_thin_card.json
{ "errors": [ { "code": "E_CASE_COUNT_THIN", "index": 1, "case_count": 1,
                "detail": "一条模式至少要有 2 道不同题目支撑，否则就是对单题下长期判断" } ],
  "passed": false }                                      exit=1

$ python3 error_card_check.py audit --card example/bad_thin_card.json --cases example/cases_junior_thin.json
{ "errors": [
    { "code": "E_CAUSE_UNVERIFIED", "case": "T1", "method": "numeric_only",
      "detail": "核验方式不足以支持完整过程（沿用同伴 handoff_check 标准）" },
    { "code": "E_EVIDENCE_NO_CASE", "index": 2, "case": "T9",
      "detail": "引用了没有交上来的题" },
    { "code": "E_EVIDENCE_STALE", "index": 3, "case": "T3",
      "cited": "000000000000", "current": "8445ad1935d7",
      "detail": "指纹与当前题面/过程不符：引用的是旧版本证据" },
    { "code": "E_CASE_COUNT_MISMATCH", "index": 3, "case_count": 2, "matched": 1 } ],
  "passed": false }                                      exit=1
```

这里三条判据直接沿用同伴的工程标准：`numeric_only` 不算完整核验（同伴 `handoff_check.py` 第 59 行）、
`T9` 引用了不存在的题、指纹过期说明**引用的是旧版本的证据**。

**教具三 · `bad_practice_card.json`——归因合格但出题不合格。** 前两道门放行，第三道驳回：

```
$ python3 error_card_check.py validate --card example/bad_practice_card.json
{ "errors": [], "warnings": [], "passed": true }         exit=0

$ python3 error_card_check.py practice --card example/bad_practice_card.json --verify-answers
{ "errors": [
    { "code": "E_DIFFICULTY_UNKNOWN", "missing": ["综合拔高"], "detail": "三档难度必须全部出现" },
    { "code": "E_PATTERN_UNCOVERED", "pattern_ref": 3, "pattern": "过程规范松动",
      "detail": "该模式一道题都没覆盖：三块短板漏一块等于没做个性化" },
    { "code": "E_ANSWER_LINEAR_UNSAT", "id": "P3",
      "equations": ["2x=4"], "claimed": { "x": "5" }, "solved": { "x": "2" },
      "detail": "代入答案不成立：本门唯一真算一次的地方" } ],
  "passed": false }
exit=1
```

**这三份教具合起来证明了"三道门各管一段"**：结构门管长得对不对，
证据门管有没有瞎引用，出题门管题出得对不对、答案算得对不对。谁都不越权。

### 52 条判据全部有真实触发

```
$ python3 verify_all_gates.py
== validate ==
   命中 19/19 个码
   未命中：（无）
== audit ==
   命中 22/22 个码
   未命中：（无）
== practice ==
   命中 18/18 个码
   未命中：（无）

结论：全部判据都有真实触发
exit=0
```

这个核验脚本分两部分：`example/` 里的真实示例卡，以及**内存里临时构造的畸形卡**
（"每一条码背后都有一次真实触发"这句话的证据）。其中三条告警
（`W_ALL_SAME_CAUSE`、`E_EVIDENCE_UNSUPPORTED`、`E_COMMONALITY_WEAK`）
只能靠合成输入演示，脚本里注明了原因——例如 `E_EVIDENCE_UNSUPPORTED` 需要
"证据里所有关键词都找不到"，而代数题面里的 `x` 几乎总会出现，所以它只对中文纯几何题面敏感。

## 与上游 `jrhhhh/math-homework-agent` 的关系

同伴仓库不是"一个错题诊断 skill"，而是**两 skill + 调度 + 交接协议 + 回归测试**的完整项目。
本技能与它有三处接口约定、两处立法对齐，全部经过逐字比对（见 [CONFLICTS.md](CONFLICTS.md)）。

### 1）为什么"出题"不违反上游禁令

上游两侧对出题的态度**看似矛盾**：

| 上游位置 | 原文 |
| --- | --- |
| `math-error-diagnosis/SKILL.md` 第 61 行 | 「默认不另出练习，不必重写整题」 |
| `math-error-diagnosis/SKILL.md` 第 66 行 | 「**只有用户请求时生成同类练习，先核验题目条件、解和完整性**，是否展示答案遵从用户要求」 |
| `solution-refiner/SKILL.md` 第 36 行 | 「不出变式题、不排复习计划……」 |

**同伴禁的是"未经请求就把题塞进诊断/优化交付物"，不是"出题"。**
他在诊断技能里亲手写下了允许出题的条件。本技能**逐条对齐**：

| 上游前提 | 本技能的落点 |
| --- | --- |
| ① 只有用户请求时 | `practice_authorized` 授权标记 + `E_PRACTICE_UNAUTHORIZED` / `E_PRACTICE_MISSING` |
| ② 先核验题目条件、解和完整性 | `practice --verify-answers`：`E_ANSWER_LINEAR_UNSAT`（精确有理数代回）、`E_ANSWER_DOMAIN_VIOLATION`、`E_ANSWER_MISSING` |
| ③ 答案展示遵从用户要求 | `student_prompt` 与 `answer` / `solution_steps` **分离**；`E_ANSWER_IN_PROMPT` 抓泄漏 |
| （本技能追加）个性化要有依据 | `pattern_ref` 绑定 + `case_count ≥ 2` 才准出题 + `E_PATTERN_UNCOVERED` |

**并且** `A_VARIANT` 不取消、只收窄口径：只在**非 `practice_items` 字段**里抓变式题措辞。
"练习合法、夹带非法"由此是一条可执行的门，而不是一句自我辩解。

### 2）三处立法对齐

| 上游立法 | 本技能的接续方式 |
| --- | --- |
| `math-error-diagnosis` §3「不贴'粗心''基础差'等标签」 | `W_LANGUAGE` 只把**对人不对事**算告警；更强的稳定判定由 `A_STABLE_JUDGMENT` 驳回 |
| `solution-refiner` Rule 2「**不凭一道题认定学生长期能力弱**」 | 把焦点搬到**样本量**：`E_CASE_COUNT_THIN` / `E_PATTERN_EVIDENCE_THIN` / `E_CASE_COUNT_MISMATCH` + `W_TENTATIVE`（必须写"假设/待验证"） |
| `handoff_check.py` 第 59 行「`numeric_only` 不足以支持完整过程」 | `E_CAUSE_UNVERIFIED`：廉价核验的错因结论**不准作为证据** |

### 3）退出码语义对照

| 脚本 | 0 | 1 | 2 |
| --- | --- | --- | --- |
| 同伴 `scripts/handoff_check.py` | 元信息与版本准入 | 有效包未满足准入 | 非法输入或缺字段 |
| 本技能 `error_card_check.py` | 门通过 / 干净 | 结构不合格 / 有越界 / 出题不合格 | 输入非法 |

**四个脚本共用同一套退出码约定**，便于宿主串联；但**它们查的东西完全不同，不可互相替代**。
本技能**不共用同伴的交接通道**——他的协议是**单题准入**（"这题够不够格去优化"），
本技能是 **N 题 × 已修复 → 聚合**，需求不同。

### 4）同伴明确不做的那一块

`math-error-diagnosis/SKILL.md` 结尾原话：

> 本技能**不自行持久化学生档案**。跨会话记忆、工具权限、OCR、独立验证和外部作业库**由宿主提供**。

**跨题的第二次归因正是同伴主动让出来的那一格**，本技能填的就是它。

## 脚本的诚实边界

- 三道门**都不是数学判断**：`validate` 只查形状，`audit` 只查措辞与引用，
  `practice` 只查绑定关系与一小类题的答案。**"这三条模式是不是真的共享"只能靠人读出来。**
- `case_count` 与 `cause.method` 都是**声明值**：脚本查得出虚报与廉价核验，
  **查不出同伴那次审查是否真的做过**。
- `E_ANSWER_LINEAR_UNSAT` 覆盖范围**很窄**：只有能解析成一元/二元一次方程（组）的题。
  二次方程、几何、证明、应用题一律 `skipped`。**能算的真算，算不了的明说。**
- **出题器与答案验证器由同一作者编写，存在循环依赖**：即使脚本真的算了，
  这也只是**工具辅助核验**，不是独立验证（同伴明确禁止把同一助手重做称为独立验证）。
- `E_PRACTICE_DUP` 只做**结构去重**；"两道不同的题其实考一件事"抓不住。
- `E_DIFFICULTY_UNKNOWN` 只查三档**是否都出现**，查不出难度标注是否名副其实。
- 三道门都通过，也只说明"卡片长得对、证据绑得对、一小类答案代回成立"，
  **不证明教学质量，也不证明归因在数学上成立。**

## 给 agent 的安装 / 测试提示词

> 请把 `error-atlas/` 作为技能安装到你的技能目录，然后用它完成冒烟测试：
>
> 1. 读取 `example/cases_junior.json`（6 道已修复错题，每道带同伴错因结论），
>    为它们生成一张错题病理图，跑 `validate` 与 `audit` 两道门，
>    **把脚本的真实 JSON 输出原文贴给我**，并说明这张卡有没有越界、每条模式的证据是否够。
> 2. 然后**我明确要求**针对这些模式出题：生成 5 道练习，每题绑定一个模式、
>    覆盖三档难度，跑 `practice --verify-answers`，并告诉我哪些题的答案是脚本真算过的、
>    哪些被 skipped 及原因。
> 3. 最后把卡片故意改坏三处——写上"你之所以错是因为审题太快"（自产错因）、
>    把某条模式的 `case_count` 改成 1（样本量不足）、把某道练习的答案改成错的
>    ——重跑三道门，解释为什么每一次是被**哪一道门**驳回的。

（提示：正确的 agent 应当**先读题与读同伴结论**再生成卡片，三道门都跑、如实引用脚本输出，
对被驳回的坏卡片逐条指出越界位置与判据码，而不是含糊地说"基本可用"。
改坏后 `validate` 可能仍会放行——结构没变；`audit` 与 `practice` 才会分别抓到
自产错因/样本量不足与答案错误。**这正是三道门的分工：结构门管长得对不对，
证据门管有没有瞎引用，出题门管题和答案对不对。**）

**Windows 注意**：`PATH` 里的 `python` / `python3` 可能是应用商店的占位程序，
运行时会静默失败、什么都不输出。若如此请用真实解释器的完整路径，例如本机为
`"D:/Program Files/anaconda3/python.exe"`。
