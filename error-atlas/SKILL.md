---
name: error-atlas
description: 学生**已经修好**若干道错题、手里有 ≥2 道题的错因结论时，横向聚合这些错题，找出跨题共享的错误模式，输出一张错题病理图（恰好 3 条模式 + 跨题共同点 + 仍成立的优势 + 一个待验证的能力训练目标）；并在学生明确要求时，按这些模式定制 5 道练习（每题绑定它治哪个模式、三档难度）。只做归纳与定制出题，不重新诊断单题错因，也不对单题下长期能力判定。Use when a student brings 多道错题、错题本、一摞错因结论、错题汇总、总复习前梳理, or asks 我总在同一类地方出错 / 我老是犯同一个错 / 这些错题有什么共同点 / 帮我看看我的错误有没有规律 / 我的薄弱能力到底是哪一块 / 错题病理 / 归纳错因 / 错误模式分析 / 能力画像 / 我该练哪一项能力. Also use when they then ask for 举一反三 / 针对我的错题出题 / 给我出几道类似的题 / 专门练这个毛病 / 定制练习 / 按我的错题出题 / 出一套只治我这个问题的题 —— 但出题必须先有归因（≥2 道错题）且学生明确要求，两者缺一不可。Do not use for 单道题的错因诊断、首错定位、修复句（那是同伴 math-error-diagnosis 的地盘）；Do not use for 答案正确时的解法优化（那是 solution-refiner）；Do not use for 学生还没动笔时的思路启动（那是 presolve-starter）；Do not use for 通用题库式出题（不绑定错误模式的"给我来 5 道圆锥曲线题"不属于本 skill）；也不接只有一道题的输入 —— 一题无法归纳，请先用 math-error-diagnosis 再攒几道。
---

# skill：Error Atlas（错题病理归因与个性化出题）

学生交来 **≥2 道已经修好的错题**（每道都带同伴给出的错因结论）时，本 skill 做两件事：

1. **错题归因整理**：横向聚合，找出跨题共享的**错误模式**，给出一张**错题病理图**
   ——3 条模式 + 跨题共同点 + 仍成立的优势 + 一个**待验证**的能力训练目标。
2. **举一反三**（**仅在学生明确要求时**）：按这些模式定制 **5 道练习**，
   每题绑定它治哪个模式，覆盖三档难度。

**只回答两个问题**：我这一批错题共享哪个模式？我该拿什么题练它？
**不回答**：这道题错在哪（同伴的事）、答案对了怎么更好（`solution-refiner` 的事）。

## 与上游的关系（两条硬约束，先读这段）

本 skill 接在同伴 `math-error-diagnosis` 的**下游**，并与之有两处立法冲突需要显式对齐：

1. **同伴禁止"不凭一道题认定学生长期能力弱"**（`solution-refiner` Core Rules 2；
   `math-error-diagnosis` §3"不贴粗心/基础差等标签"）。本 skill 做跨题断言，
   因此把立法焦点从"能不能说"搬到"**样本够不够**"：
   每条模式必须 `case_count ≥ 2` 且证据里**点名**够题数，画像必须带"假设/待验证"限定词。
   **这是接续同伴的立法，不是绕过它。**
2. **同伴禁止"未授权出题"**（`solution-refiner`："不出变式题"），
   但他**亲手写出了允许出题的条件**——`math-error-diagnosis` §4：
   > 「只有用户请求时生成同类练习，**先核验题目条件、解和完整性**，是否展示答案遵从用户要求。」

   本 skill 的出题通道**逐条对齐这三个前提**：授权标记门、答案核验门、题干与答案分离。
   **练习合法，夹带非法**——借归因字段塞题目会被 `A_VARIANT` 驳回。

## 三条接口约定（必须遵守，脚本会查）

### ① 输入 `--cases` 的结构

每道错题必须带**同伴结论对象**：

```json
[
  {"id": "T1", "grade_level": "初中",
   "problem": "…", "student_solution": "…",
   "cause": {"type": "运算错误", "summary": "…",
             "method": "assistant_review",
             "scope": "第 2 步移项到第 3 步结论",
             "unresolved_items": []}}
]
```

- `cause.type` **只能**取同伴 `references/error-types.md` 的六类：
  `运算错误` / `条件失效` / `分支/边界遗漏` / `逻辑错误` / `定理误用` / `论证缺口`
  ——**原样沿用，不改名、不细分**。
- `cause.method` **只能**取同伴五值：`assistant_review` / `independent_review` /
  `tool_assisted_review` / `numeric_only` / `none`。
  **后两者不准入**：核验方式不足以支持完整过程。
- `cause.unresolved_items` 必须为空：还有待解决事项的题不能当已闭合证据。

### ② 证据引用必须带内容指纹

`evidence` 必须写成 `[题号#12位指纹] …`，指纹算法与同伴 `scripts/handoff_check.py`
的 `version()` **逐字相同**（取前 12 位十六进制）：

```python
fingerprint = hashlib.sha256(json.dumps(
    {"grade_level": grade, "problem": problem, "student_solution": solution},
    ensure_ascii=False, sort_keys=True, separators=(",", ":"),
).encode("utf-8")).hexdigest()[:12]
```

`example/build_cards.py` 就是按这个算法生成示例卡的——**不要手写指纹**。
指纹对不上会报 `E_EVIDENCE_STALE`（学生保留题号但换了题面，引用就静默失配）。

### ③ 退出码语义与同伴一致

`0` 准入 / 通过 · `1` 有效但不准入 · `2` 非法输入。三道门都遵循这个约定，
但**查的东西完全不同，不能互相替代**。

## Core Rules

1. **只归纳，不重新诊断。** 错因只能**引用**同伴结论（`E_CAUSE_TYPE_MISMATCH` 查引用是否忠实）。
   不许自产错因（`A_NEW_CAUSE`）、不许否定同伴结论（`A_OVERRIDE`）、
   不许对单题重新判错（`A_SINGLE_CASE_CAUSE`）。
2. **跨题断言必须过样本量。** 每条模式 `case_count ≥ 2`，且 `evidence` 里**点名**的题数
   不得少于声明的 `case_count`；3 条里至少要 2 条达标。**一条题错的模式不准用来出题。**
3. **只下统计假设，不下稳定判定。** `capability_profile` 必须带"假设 / 待验证 / 暂定"
   限定词（`W_TENTATIVE`），不许出现"一直很弱""长期能力不足"（`A_STABLE_JUDGMENT`）。
4. **必须举证优势。** `strength_kept` 是**强制字段**：只说缺点会退化成黑名单。
5. **出题需要显式授权，且必须先有归因。** `practice_authorized=true` 只在学生明确要求时写；
   未授权时 `practice_items` 必须是空数组。
6. **每道练习题必须绑定一个模式**（`pattern_ref`），且该模式 `case_count ≥ 2`、
   三个模式**都要被覆盖**。绑定关系就是"个性化"的技术定义，没有它这个功能等于题库。
7. **必须过门，未过门不得交付。** 退出码是唯一裁决，不信自己"我觉得没问题"。
8. **越界即停。** 不做单题诊断、不做正解优化、不做通用题库、不排复习计划、
   不给评分、不报置信度、不探测理解深度——那些属于别的 skill。

## 卡片格式

一个 JSON 对象，恰好八个顶层字段，全部必需：

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `error_patterns` | object[] | **恰好 3 条**，每条六字段，见下 |
| `cross_case_commonality` | string | 一句话，需点到**至少 2 个不同题号** |
| `strength_kept` | string | 这批错题里**仍然成立**的一项能力 |
| `capability_profile` | string | 跨案例**假设性**画像，需含限定词，聚焦**一个**能力标签 |
| `next_training_target` | string | **恰好一个**能力标签或聚合维度 |
| `practice_authorized` | bool | 无明确请求必须为 `false` |
| `practice_items` | object[] | 授权时**恰好 5 条**；未授权必须为 `[]` |
| `generation_basis` | string | 授权时必填：点名至少一个模式与至少两个题号 |

`error_patterns` 每条恰好六字段：

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `pattern` | string | 取自**下表**（同义写法会被归一） |
| `cause_type` | string | 取自**同伴六类** |
| `evidence` | string | 以 `[题号#12位指纹]` 开头；正文关键词要能在该题原文或同伴结论里找到 |
| `case_count` | int | 支撑本模式的**不同题目数**，`≥ 2`，且不超过证据里点名的题数 |
| `capability_hypothesis` | string | 必须落在下表对应行 |
| `countermeasure` | string | 一个**能立刻做的动作**（不是周期计划） |

`practice_items` 每条恰好七字段：

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `id` | string | 唯一，如 `P1` |
| `pattern_ref` | int | `error_patterns` 的 **1 基序号**，且该模式 `case_count ≥ 2` |
| `difficulty` | string | `同型巩固` / `变式迁移` / `综合拔高`，三档**都必须出现** |
| `student_prompt` | string | **学生可见题干**，只含条件与所求，不含任何解法或答案 |
| `answer` | string | 标准答案 |
| `solution_steps` | string | 简版解法，供家长/教师核验，**不给学生** |
| `source_pattern` | string | 须与 `pattern_ref` 对应的 `pattern` 一致 |

## 两份词表（**不同维，别混**）

### 跨题聚合维度（学生维度：哪种加工反复失败）

| `pattern` | `capability_hypothesis` | 同义写法 | 典型表现 |
| --- | --- | --- | --- |
| 条件加工缺位 | 条件提取与转译 | 审题不清 / 审题漏条件 | 反复漏定义域、范围、非零约束 |
| 分支穷尽不足 | 逻辑完备性 | 分类讨论不全 / 漏讨论 | 反复漏情形、边界不单独讨论 |
| 前提检验缺位 | 定理适用性判断 | 定理误用 | 反复直接用定理而不核前提 |
| 概念边界混淆 | 概念辨析 | 概念混淆 | 反复把充分当必要、混淆定义 |
| 过程规范松动 | 步骤留痕与记录 | 计算跳步 / 条理不清 | 反复心算跳步导致连环错 |
| 结果自检缺位 | 自我验证 | 检验缺位 | 反复不代回、不估算，错解照交 |
| 表达精度不足 | 数学语言 | 表达不严谨 | 反复写"约为"、缺单位或范围 |

### 同伴六类（题目维度：这一步属于哪类判断尺度）

`运算错误` / `条件失效` / `分支/边界遗漏` / `逻辑错误` / `定理误用` / `论证缺口`

> **口径**：`pattern` 是"哪种加工反复失败"，`cause_type` 是"这道题这一步属于哪类判断"。
> 同一张卡里，三对 `(pattern, cause_type)` 各自成立、互不推导。
> 上表**不替代、不细分**同伴的六类——原稿里与之重名的五条已删除。

学段切换的是**用词，不是结构**：小学说"又看漏了'剩下的'"，初中说"又忘了检验是否有实根"，
高中说"又没验证判别式符号"，大学说"定理前提（连续性/可积性）又没核"。

## Workflow

四道命令。**第一段两道门，第二段一道门**；签名如下。
（三道门合计 **59 条判据**：结构门 19 · 证据/引文/越界门 22 · 出题/答案核验门 18。）

### 第 0 步（可选）：两份菜单

```bash
python3 error_card_check.py patterns --problem "已知二次函数 f(x)=x^2-4x+3，求它与 x 轴交点的个数。"
```

打印聚合维度表 + 同伴六类，并给关键词初判。**它只是提示，不能替代读题。**

### 第一段：归因

1. **读题与读错因结论**（必须自己读）。逐题确认：题面、学生过程、同伴结论是否齐全。
   缺 `cause` 或 `cause.method` 是 `numeric_only`/`none` → **先让对方跑同伴的 skill**，不要自己补诊断。
2. **算指纹、生成卡片**。参考提示词：

   ```text
   你是错题病理归因器。学生交来若干道已修好的错题，每道都带同伴的错因结论。
   规则：不重新诊断单题错因，只能引用同伴结论（cause_type 用同伴六类原词）；
   不许对单题下长期能力判定；跨题模式必须有 ≥2 道题支撑，evidence 里要点名题号；
   capability_profile 必须写成"假设/待验证"口吻；必须举证一项仍然成立的优势；
   恰好 3 条 error_patterns + 1 条跨题共同点 + 1 项优势 + 1 个训练目标。
   只输出 JSON。学段：{{grade_level}}  错题与结论：{{cases}}
   ```

3. **结构门**：

   ```bash
   python3 error_card_check.py validate --card card.json
   ```

   退出码 `0` 通过 · `1` 结构不合格（字段/三条/双词表/样本量/指纹格式/画像聚焦）· `2` 输入非法。

4. **证据门 + 引文门 + 越界门**（必须带 `--cases`）：

   ```bash
   python3 error_card_check.py audit --card card.json --cases cases.json
   ```

   退出码 `0` 干净 · `1` 发现 error · `2` 输入非法。加 `--strict` 时 warning 也算失败。

### 第二段：出题（**仅当学生明确要求**）

5. **先确认授权**。学生没说"出题/举一反三/针对我的错题练"，就**停在这里交付病理图**，
   把 `practice_authorized` 写成 `false`、`practice_items` 写成 `[]`。
6. **出题门 + 答案核验门**：

   ```bash
   python3 error_card_check.py practice --card card.json --verify-answers
   ```

   退出码 `0` 通过 · `1` 出题不合格 · `2` 输入非法。
   授权门 / 绑定门（`pattern_ref`、样本量、覆盖、三档难度、去重）/
   答案核验门（`E_ANSWER_IN_PROMPT`、`E_ANSWER_UNRELATED`、`E_ANSWER_LINEAR_UNSAT`、
   `E_ANSWER_DOMAIN_VIOLATION`）分工明确，看 `code` 就知道改哪里。

7. **未过门就定点修**，最多 3 轮；3 轮仍不过，如实报告卡在哪一条并贴脚本原文，
   不许降级交付。修的时候把脚本输出喂回去让它**只改被指出的字段**，别整张重生成。
8. **交付**：
   - 第一段产物 —— 卡片 JSON + 两道门真实输出 + 用教学语言讲 3 条模式
     （把 `capability_profile` 讲成"**初步看是……，还要用新题验证**"）。
   - 第二段产物（若已授权）—— **学生版只给 `student_prompt` 与 `source_pattern`**，
     `answer` / `solution_steps` 另存给家长或教师；提醒"做完先自己核对，再对答案"。

## Output Standards

- 必须附脚本的**真实 JSON 输出**；跑不了就明说"未验证"，不许编造输出。
- 分开三类结论：**结构裁决**（validate）· **证据与越界**（audit 的 errors / warnings）·
  **出题与答案核验**（practice 的 errors / `answer_verification`）。
- 把卡片翻译回教学语言交给学生，别直接甩 JSON。
- 讲 `capability_hypothesis` 时对事不对人：说"这批题里反复出现……"，不说"你能力差"。
- 交付时**主动说明哪些题被 `skipped`**（超出答案核验范围），别让"通过"读起来像"全验过了"。

## Prohibited Behavior

- 没有通过证据就交付卡片。
- 自产错因、否定同伴结论、对单题重新判错（那是 `math-error-diagnosis` 的活）。
- 用少于 2 道题的模式下判断，或写"一直很弱""长期能力不足"这类稳定判定。
- **未经明确请求就出题**，或把题目塞进归因字段（`A_VARIANT`）。
- 出题时不绑定模式、不覆盖全部模式、三档难度缺档、答案泄漏进题干。
- 出变式题（练习之外）、排复习计划、给评分、报置信度、探测理解深度。
- `audit` / `practice` 报了 error 却说成"基本可用"之类含糊措辞。

## 能力边界（别把它当保证）

- 三道门**都不是数学判断**：`validate` 查形状，`audit` 查措辞与引用，
  `practice` 查绑定关系与一小类题的答案。"这三条模式是不是真的共享"只能靠人读出来。
- `case_count` 与 `cause.method` 都是**声明值**：脚本查得出虚报（`E_CASE_COUNT_MISMATCH`）
  与廉价核验（`E_CAUSE_UNVERIFIED`），**查不出同伴那次审查是否真的做过**。
- 证据门是**关键词匹配且忽略个位数字**；证据里提到的变量（如 `x`）几乎总能在题面里找到，
  所以 `E_EVIDENCE_UNSUPPORTED` 只对**不含 ASCII 符号的中文题面**敏感。
- `E_ANSWER_LINEAR_UNSAT` 只用精确有理数覆盖**可解析为一元/二元一次方程（组）**的题；
  二次方程、几何、证明、应用题一律 `skipped`，**不假装验过**。
- 出题器与答案验证器**由同一作者编写，存在循环依赖**：即使脚本真的算了，
  这也只是**工具辅助核验**，不是独立验证（同伴明确禁止把同一助手重做称为独立验证）。
- `E_PRACTICE_DUP` 只做**结构去重**；"两道不同的题其实考同一件事"抓不住。
- 三道门都通过，也只说明"卡片长得对、证据绑得对、一小类答案代回成立"，
  **不证明教学质量，也不证明归因在数学上成立**。

## 安装与冒烟测试

完整走一遍的例子（六道错题 → 病理图 → 定制练习，含学生版题纸与答案页）见
`example/DEMO.md`；它引用的每段 JSON 都是真实运行结果。

```bash
# 全部示例与门的真实输出（含 52 条判据的覆盖核验）
python3 example/build_cards.py
python3 error_card_check.py validate --card example/junior_three_cases.json
python3 error_card_check.py audit --card example/junior_three_cases.json --cases example/cases_junior.json
python3 error_card_check.py practice --card example/practice_with_answers.json --verify-answers
python3 verify_all_gates.py
```

**Windows 注意**：`PATH` 里的 `python` / `python3` 可能是应用商店的占位程序，
运行时会静默失败、什么都不输出。若如此请用真实解释器的完整路径，例如本机为
`"D:/Program Files/anaconda3/python.exe"`。
