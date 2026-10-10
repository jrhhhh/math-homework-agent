# error-atlas · 错题病理归因与个性化出题 —— 设计稿

> 《数学智能体工程与实践》第 4 讲动手作品第三件，与 `my_skill/`（presolve-starter）、
> `solution_refiner/`（solution-refiner）并列。
>
> **两段式 skill**：第一段**错题归因整理**（≥2 道已修复错题 → 跨题模式 → 能力假设），
> 第二段**举一反三·个性化定制题目**（把模式变成学生自己的练习，每题绑定它治哪个模式）。
>
> 本文件是**设计稿**：分工表 + description + 卡片 schema + **三道门**的判据清单。
> 设计定稿后再生成 `SKILL.md` / `error_card_check.py` / `example/` / `README.md`。
>
> ✅ **已落地**，实际规模以脚本与覆盖核验为准：**59 条判据**
> （结构门 19 · 证据/引文/越界门 22 · 出题/答案核验门 18），
> `verify_all_gates.py` 输出"全部判据都有真实触发"，原始输出见 `real_output.txt`。
> 本稿下面的清单是设计依据，实现以 `error_card_check.py` 为准。
>
> ⚠️ **已按上游冲突核查修订**：见 [CONFLICTS.md](CONFLICTS.md)。该文件比对了同伴仓库
> `jrhhhh/math-homework-agent` 的**实际内容**（两个 skill + 交接协议 + 门脚本），
> 查出 3 处真冲突（其中一处踩在同伴明写的"不凭一道题认定学生长期能力弱"的红线上），
> 并结清了"出题是否违反上游禁令"这一条（结论：不冲突，但须满足三个强制前提）。
> 凡"★修订/★新增"处以此稿为准。

---

## 一、这块疆域为什么是空的

同伴的错题诊断 skill 回答的是"**这一道题**错在哪、怎么补"。它每跑一次，
产出一份**单题病灶**。学生一学期攒下二十份病灶，然后呢？——没有然后。

工具链上没有人管**跨题的第二轮工作**：

| 问题 | 谁回答 | 答案的性质 |
| --- | --- | --- |
| 这道题我错在哪？ | **同伴**（错题诊断） | 单题 · 已发生 · 病灶 |
| 我这一批错题**共享**哪个模式？ | **本 skill 第一段** | 跨题 · 统计性 · 资产 |
| 那我该做哪些题？ | **本 skill 第二段** | 个性化 · 绑定模式 · 可练 |
| 答案对了但笨？ | `solution_refiner` | 单题 · 优化空间 |
| 根本不会开始？ | `presolve_starter` | 单题 · 启动思路 |

**一句话**：同伴管"从错到对"，`solution_refiner` 管"从对到好"；
本 skill 管"**从一摞错题到一个可训练的能力目标，再到一套只治你那些毛病的题**"。

> ★**出题这一格为什么也是空的**：上游两侧都不占——`math-error-diagnosis` 只在
> "用户请求时生成同类练习"（且它自己不做持久化，攒不了模式）；`solution-refiner`
> 把"出变式题"明列为**禁止行为**。于是"**基于跨题归因的个性化出题**"没有任何人做。
> 而它恰好是同伴**允许**的那条通道——见 5.1。

### 1.1 与同伴的联系：明确的上下游，不是并列

这是本 skill 与 `solution_refiner` 最大的不同——它不是"另开一处"，
而是**接在同伴下游、消费同伴的产出**：

```
   一道题做错
        ↓
   同伴：错因诊断 → 最小修改 → 分层提示        （产出：单题错因结论）
        ↓  学生把若干条错因结论 + 对应题目原文交过来
   本 skill 第一段：横向聚合 → 共享模式 → 能力假设
        ↓  用户明确要求出题（授权门）
   本 skill 第二段：按模式定制 5 题，每题绑定它治哪个模式
        ↓  做完又错 → 回到同伴诊断
```

**接口约定（写进 description，且由门强制执行）**：本 skill **要求输入同伴给出的错因结论**，
且该结论必须**来自一次真实审查**——`cause.method` 只能是
`assistant_review` / `independent_review` / `tool_assisted_review` 三值之一，
`numeric_only` / `none` **不准入**，`cause.unresolved_items` 必须为空（判据见 4.2）。
学生没带可引用的结论时，本 skill 不自己重新诊断——**先让对方跑同伴的 skill**。
这是 `A_NEW_CAUSE` 与 `E_CAUSE_*` 三条门的立法理由。

★**与上游的核心立法对话**：同伴明确禁止"不凭一道题认定学生长期能力弱"。
本 skill 做跨题断言，因此把立法焦点从"能不能说"搬到"**样本够不够**"：
每条模式必须 `case_count ≥ 2`，`capability_profile` 必须带"假设 / 待验证"限定词。
**这是与同伴立法的接续，不是绕过它**——见 [CONFLICTS.md](CONFLICTS.md) 冲突 1。

### 1.2 与同伴的区别：七个正交维度

| 维度 | 同伴（错题诊断） | error-atlas |
| --- | --- | --- |
| **输入规模** | 1 道题（+ 学生解答） | **≥ 2 道题**（+ 每题的错因结论） |
| **产出对象** | 病灶：错因、修复句 | 资产：**跨题共享模式**、能力假设 |
| **真值来源** | 学生这一次的推理链 | 同伴的错因结论 + 题目原文 |
| **裁决方向** | 面向当下：这题怎么办 | 面向未来：**下一个该练什么** |
| **时间尺度** | 一次性 | 累积性（错误率随历史变化） |
| **出题** | ★默认不出；仅"用户请求时生成同类练习" | ★**按模式定制出题**（`pattern_ref` 绑定，见 §五） |
| **断言强度** | 单题可下判断（"这一步错了"） | ★只能下**统计假设**（`case_count ≥ 2` + "待验证"限定词） |

### 1.3 与 presolve_starter / solution_refiner 的区别

- `presolve_starter`：**事前**，学生还没动笔 → 给启动动作。
- `solution_refiner`：**事后·对**，学生做对了 → 给优化方向，且**禁止出变式题**。
- **本 skill**：**事后·错·且已修**，且**≥ 2 题** → 先是能力**假设**，再是**只治这些毛病的题**。

四者共用同一套"卡 + 门"工程骨架，但**卡片 schema、证据要求、门的判据全都不同**
——这是新功能的落点，不是重复劳动。本 skill 是四件里**唯一有第二段产物**的：
前三个技能都只产出一张卡，它产出**病理图 + 个性化练习**两份东西、三道门。

---

## 二、第一段：一张错题病理图

学生交来 N 份（**N ≥ 2**）"题目原文 + 学生当时的解法 + **同伴给出的错因结论**"，本 skill 产出一张卡：

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `error_patterns` | object[] | **恰好 3 条**，每条五字段（见下） |
| `cross_case_commonality` | string | 一句话，必须点到**至少 2 个不同题号** |
| `strength_kept` | string | 这批错题里**仍然成立**的一项能力（强制项，见 2.2） |
| `capability_profile` | string | ★修订：跨案例**假设性**画像，必须含"假设 / 待验证 / 暂定"类限定词（原名 `overall_diagnosis`——**与上游同名字段语义相反**，已弃用） |
| `next_training_target` | string | ★修订：**恰好一个**能力标签；不是"多练练"（原名 `next_step`——**与上游同名字段语义相反**，已弃用） |
| `practice_authorized` | bool | ★新增：授权标记。**无用户明确请求必须为 `false`**，此时 `practice_items` 必须为空数组 |
| `practice_items` | object[] | ★新增：**恰好 5 条**（`practice_authorized=true` 时），每条七字段，见 §五。**每道题必须绑定一个 `error_pattern`** |
| `generation_basis` | string | ★新增：出题依据一句话，需点名**至少一个** `pattern` 名与**至少一个**题号（`practice_authorized=true` 时必填） |

`error_patterns` 每条恰好五个字段：

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `pattern` | string | 取自**跨题聚合维度表**（2.1）；**不是**对同伴 6 类错误分类的替代或细分 |
| `cause_type` | string | ★新增：**只能**取同伴 `references/error-types.md` 的六类之一——"引用同伴结论"的类型化通道 |
| `evidence` | string | ★修订：**必须以 `[题号#指纹]` 开头**（指纹 = 同伴同款 SHA-256 前 12 位），正文需能在该题原文中找到（见 4.2） |
| `case_count` | int | ★新增：支撑本模式的**不同题目数**，必须 `≥ 2`；`1` 即驳回（与"不凭一道题定长期能力"的立法分界） |
| `capability_hypothesis` | string | ★修订：与 `pattern` 对应的**能力假设**（原名 `root_capability`——措辞像稳定判定，已改名） |
| `countermeasure` | string | 一个**能立刻做的动作**（✗「以后注意审题」✓「下次读题先圈出所有取值范围条件」） |

### 2.1 跨题聚合维度表（本 skill 的核心词表）

★**与上游的关系必须先说清**（这是冲突 2 的修法）：同伴的
`references/error-types.md` 六类（运算错误 / 条件失效 / 分支·边界遗漏 / 逻辑错误 / 定理误用 / 论证缺口）
是**题目维度**的**判断尺度**——用于"这一步证据是什么、怎么补"。
下表是**学生维度**的**聚合维度**——用于"多道题合起来反复出现哪种加工失败"。

**两者不同维，因此：**

- 同伴的六类**原样沿用**为 `cause_type`，**不改名、不细分**；
- 我这张表**不替代、不细分**同伴的分类，只用于 `capability_hypothesis`；
- 原稿与之重名的五条（审题漏条件 / 符号处理 / 前提检验缺位 / 分类讨论不全 / 计算跳步）
  **已删除**——它们在同伴那里分别叫条件失效 / 运算错误 / 定理误用 / 分支·边界遗漏 / 运算错误。

| 聚合维度（`pattern`） | 能力假设（`capability_hypothesis`） | 典型表现 |
| --- | --- | --- |
| 条件加工缺位 | 条件提取与转译 | 反复漏定义域、范围、非零约束 |
| 分支穷尽不足 | 逻辑完备性 | 反复漏情形、边界不单独讨论 |
| 前提检验缺位 | 定理适用性判断 | 反复直接用定理而不核前提 |
| 概念边界混淆 | 概念辨析 | 反复把充分当必要、混淆定义 |
| 过程规范松动 | 步骤留痕与记录 | 反复心算跳步导致连环错 |
| 结果自检缺位 | 自我验证 | 反复不代回、不估算，错解照交 |
| 表达精度不足 | 数学语言 | 反复写"约为"、缺单位或范围 |

> **判据口径**：`pattern` 是"哪种加工反复失败"（学生维度），`cause_type` 是"这道题这一步属于哪类判断"
> （题目维度）。同一张卡里，三对 `(pattern, cause_type)` 各自成立、互不推导。

> 学段切换的是**用词，不是结构**：小学说"又看漏了'剩下的'"，初中说"又忘了检验是否有实根"，
> 高中说"又没验证判别式符号"，大学说"定理前提（连续性/可积性）又没核"。

### 2.2 为什么强制 `strength_kept`（这是纪律，不是装饰）

同伴的诊断只有"病灶"，攒多了会变成一份**全是缺点的档案**，学生读完只会挫败。
"病理图"若只列病，就退化成"黑名单"。所以本 skill **强制要求举证一项仍然成立的能力**，
且必须在批改过的题里能找到依据。这也是与同伴在**交付语气**上的分野：
同伴可以说"这里错了"，本 skill 必须同时指出"**你哪一块是稳的**"。

---

## 三、负面触发器（description 草稿）

```yaml
name: error-atlas
description: 学生**已经修好**若干道错题、手里有 **≥2 道题**的错因结论时，
  横向聚合这些错题，找出**跨题共享的错误模式**，输出一张错题病理图
  （恰好 3 条模式 + 跨题共同点 + 仍成立的优势 + 一个待验证的能力训练目标）；
  **并在学生明确要求时**，按这些模式定制 5 道练习（每题绑定它治哪个模式、三档难度），
  只做归纳与定制出题，不重新诊断单题错因，也不对单题下长期能力判定。
  Use when a student brings 多道错题、错题本、一摞错因结论、错题汇总、总复习前梳理,
  or asks 我总在同一类地方出错 / 我老是犯同一个错 / 这些错题有什么共同点 /
  帮我看看我的错误有没有规律 / 我的薄弱能力到底是哪一块 / 错题病理 / 归纳错因 /
  错误模式分析 / 能力画像 / 我该练哪一项能力.
  Also use when they then ask for 举一反三 / 针对我的错题出题 / 给我出几道类似的题 /
  专门练这个毛病 / 定制练习 / 按我的错题出题 / 出一套只治我这个问题的题 ——
  但出题必须先有归因（≥2 道错题）且学生明确要求，两者缺一不可。
  Do not use for 单道题的错因诊断、首错定位、修复句（那是同伴 math-error-diagnosis 的地盘）；
  Do not use for 答案正确时的解法优化（那是 solution-refiner）；
  Do not use for 学生还没动笔时的思路启动（那是 presolve-starter）；
  Do not use for 通用题库式出题（不绑定错误模式的"给我来 5 道圆锥曲线题"不属于本 skill）；
  也**不接只有一道题**的输入 —— 一题无法归纳，请先用 math-error-diagnosis 再攒几道。
```

要点：

1. **输入规模写进 description**（"≥2 道题"）——最有效的负面触发器，一题场景当场挡回，
   且由 `E_TOO_FEW_CASES` 在 `audit` 里**强制执行**（不只靠措辞）。
2. **出题意图单列一组触发词**，并写明**两个前提缺一不可**（先有归因 + 学生明确要求）——
   这正是上游"只有用户请求时生成同类练习"的措辞落地。
3. **通用题库式出题明确排除**——"给我来 5 道圆锥曲线题"不接，这是与出题工具的分界（见 5.2）。
4. **上游技能名写全**（`math-error-diagnosis` / `solution-refiner` / `presolve-starter`）——
   上游两条 description 都用真名互相引用，我用真名才能接进同一套路由。
5. 触发词分三组：**名词组**（错题本、错因结论）走"持有物"路由、**提问组**（我老犯同一个错）
   走"意图"路由、**出题组**（举一反三、定制练习）走"第二段"路由。
6. **不说"能力弱"，说"待验证的能力目标"**——与上游 `solution-refiner` 的"不作稳定能力判定"对齐。

---

## 四、前两道门的判据清单

沿用你现有的骨架：纯标准库、退出码即裁决、分开"结构裁决"与"越界审计"。
本 skill 在前两道上新增**两类你现在两个脚本里都没有的门**：

- 🆕 **证据门**（该模式是否真有跨题证据）——`validate` 管格式，`audit` 管对上原文；
- 🆕 **引文门**（引用同伴结论合法，自己下新诊断非法）——`audit` 的 `A_NEW_CAUSE` 一族。

（第三道门 `practice` 见 §五。）

### 4.1 `validate --card card.json`（结构门）

★不查 `case_count` 是否对得上真实证据——那是 `audit` 的事（结构与证据分离，沿用你现有两件的分工）。

退出码：`0` 通过 · `1` 结构不合格 · `2` 输入非法（文件缺失 / JSON 坏 / 顶层不是对象）。

| 码 | 级别 | 判据 |
| --- | --- | --- |
| `E_FIELDS` | error | 顶层必须**恰好**八个：`error_patterns`/`cross_case_commonality`/`strength_kept`/`capability_profile`/`next_training_target`/`practice_authorized`/`practice_items`/`generation_basis` |
| `E_COUNT` | error | `error_patterns` 不是**恰好 3 条** |
| `E_ITEM_FIELDS` | error | 某条不是恰好五字段 `pattern`/`cause_type`/`evidence`/`case_count`/`capability_hypothesis`/`countermeasure`，或 `case_count` 不是 int |
| `E_PATTERN_UNKNOWN` | error | `pattern` 不在**聚合维度表**（2.1）内（同义写法先归一：`审题不清`→`条件加工缺位`、`条理不清`→`过程规范松动`） |
| `E_CAUSE_TYPE_UNKNOWN` | error | ★`cause_type` 不在**同伴六类**内 —— 六类名以同伴 `references/error-types.md` 为准，**不改名、不细分** |
| `E_CASE_COUNT_THIN` | error | ★任一 `case_count < 2` —— 一条模式只由一道题支撑。**这是与"不凭一道题认定长期能力"的立法分界** |
| `E_PATTERN_EVIDENCE_THIN` | error | ★3 条里达到 `case_count ≥ 2` 的**少于 2 条**（防止用一条真模式 + 两条凑数） |
| `E_GAP_UNKNOWN` | error | `capability_hypothesis` 不在聚合维度表对应行的取值域内 |
| `W_GAP_MISMATCH` | warning | `capability_hypothesis` 与 `pattern` 对应行不搭（仿 solution-refiner 的 `W_GAP_MISMATCH`） |
| `E_PATTERN_DUP` | error | 3 条里有重复 `pattern`（去重后 <3 条即报） |
| `E_EVIDENCE_FORM` | error | ★`evidence` 不匹配 `^\s*[\[【][^\]】#]+#[0-9a-f]{12}[\]】]`（**必须带 12 位十六进制内容指纹**） |
| `E_COMMONALITY_NO_IDS` | error | `cross_case_commonality` 里点到的不同题号**少于 2 个** |
| `E_PROFILE_UNKNOWN` | error | ★`capability_profile` 里出现任一能力标签，但表里没有任何一行与它对应 |
| `E_PROFILE_MULTI` | error | ★`capability_profile` 里出现 2 个及以上能力标签（画像聚焦一个） |
| `W_TENTATIVE` | warning | ★`capability_profile` 缺少"假设 / 待验证 / 暂定 / 初步"类限定词 —— 缺则读起来像稳定判定 |
| `E_TARGET_UNKNOWN` | error | `next_training_target` 没有任何能力标签 |
| `W_TARGET_MULTI` | warning | `next_training_target` 里出现 2 个及以上能力标签（应恰好一个） |
| `W_SHORT` | warning | 任一 `countermeasure` / `strength_kept` 过短（<8 字），可能敷衍 |
| `W_TEMPLATE` | warning | `countermeasure` 命中"多练练 / 注意一下 / 认真点"这类不可执行模板 |

### 4.2 `audit --card card.json --cases cases.json`（证据门 + 引文门 + 越界门）

★`--cases` 结构已按上游对齐（冲突 5）：每题必须带**同伴结论对象**。

```json
[
  {"id": "T1",
   "problem": "…", "student_solution": "…",
   "cause": {"type": "运算错误", "summary": "…",
             "method": "assistant_review",
             "scope": "第 2 步移项到第 3 步结论",
             "unresolved_items": []}}
]
```

`cause.type` 取同伴六类；`cause.method` 取**同伴同款五值枚举**
（`assistant_review` / `independent_review` / `tool_assisted_review` / `numeric_only` / `none`）。

退出码：`0` 干净 · `1` 发现 error · `2` 输入非法。加 `--strict` 时 warning 也算失败。

**🆕 证据门（本 skill 独有）**

| 码 | 级别 | 判据 |
| --- | --- | --- |
| `E_EVIDENCE_NO_CASE` | error | `evidence` 的题号在 `--cases` 里不存在（引用了没交上来的题） |
| `E_EVIDENCE_STALE` | error | ★`evidence` 的 12 位指纹与该题**当前内容**算出的指纹不符（题面/过程被换过）——算法与同伴 `handoff_check.py` 逐字相同 |
| `E_EVIDENCE_UNSUPPORTED` | error | `evidence` 去掉前缀后的关键词，在该题 `problem`/`student_solution`/`cause.summary` 里**一个都找不到**（仿 solution-refiner 关联度检查，**同样忽略个位数字**以免误报） |
| `E_TOO_FEW_CASES` | error | `--cases` 里的题**少于 2 道** → 无法归纳，直接驳回 |
| `E_CASE_COUNT_MISMATCH` | error | ★某条 `case_count` **大于**该条 `evidence` 实际能对上的题数（虚报样本量） |
| `E_CAUSE_MISSING` | error | ★某题没有 `cause` 对象，或 `cause.summary` 为空（没有可引用的同伴结论） |
| `E_CAUSE_UNVERIFIED` | error | ★`cause.method ∈ {numeric_only, none}` —— **核验方式不足以支持完整过程**（沿用同伴 `handoff_check.py` 第 59 行的标准） |
| `E_CAUSE_UNRESOLVED` | error | ★`cause.unresolved_items` 非空 —— 该题还有待解决事项，不能当作已闭合证据 |
| `E_CAUSE_TYPE_MISMATCH` | error | ★卡片某条的 `cause_type` 与该条证据所指题目的 `cause.type` 不一致（**引用要忠实原结论**） |
| `W_COMMONALITY_WEAK` | warning | `cross_case_commonality` 只点到题号、没点到任何聚合维度关键词 |
| `W_ALL_SAME_CAUSE` | warning | ★三条 `cause_type` 全同 —— 三种不同加工模式却归到同一类判断，可疑 |

**🆕 引文门（消费同伴产出，不许越权）**

| 码 | 级别 | 判据 |
| --- | --- | --- |
| `A_NEW_CAUSE` | error | 出现"你之所以错是因为 / 根本原因是 / 真正的问题在于"这类**自产错因**句式——错因只能**引用**同伴结论。合法写法：`[T1#a1b2c3d4e5f6] 同伴诊断为"运算错误"，原文的移项确实变了号` |
| `A_OVERRIDE` | error | 否定同伴结论：`不是运算问题` / `其实不是这个原因` |
| `A_SINGLE_CASE_CAUSE` | error | ★卡片里重新诊断**某一题**的错因（单题题号 + 错因措辞的组合）——单题诊断是同伴的活 |
| `A_STABLE_JUDGMENT` | error | ★出现稳定能力判定措辞：`一直很弱` / `长期能力不足` / `天生` / `就是不会` —— 与同伴"不凭一道题认定长期能力弱"的立法对齐；允许"反复出现""多次""这批题里"等**统计口径**措辞 |

**沿用现有两个脚本的越界门**（同一套立法理由：这些是别的 skill 的疆域）

| 码 | 级别 | 判据 |
| --- | --- | --- |
| `A_SOLVE` | error | 卡片里出现完整解法 / 本题答案泄漏（`解：`、`答案是`、`得 x=` 等） |
| `A_VARIANT` | error | ★**仅在非 `practice_items` 字段里**出现变式题措辞（`变式题` / `下面这道题` / `试试这道`）——练习本身合法，**借归因/画像字段夹带题目不合法**（口径见 5.1） |
| `A_PLAN` | error | 排复习计划（`每天…道` / `一周` / `复习计划` / `三天内`） |
| `A_SCORE` | error | 给评分（`得分` / `扣 N 分` / `正确率 8`） |
| `A_CONFIDENCE` | error | 报置信度（`置信度` / `可信度`） |
| `A_PROBE` | error | 探测理解深度（`你真的理解了吗` / `再讲讲为什么`） |
| `W_LANGUAGE` | warning | 语气对人不对事（`你太粗心` / `你就是不细心`）——★范围**小于**上游禁令：上游禁止贴"粗心/基础差"等标签，本表只算告警，且**不替代**上游那条更强禁令；范围更大的稳定能力判定由 `A_STABLE_JUDGMENT` 驳回 |

> **`A_PLAN` 与 `countermeasure` 的分界（最容易被误伤，必须在 SKILL.md 写清）**：
> 训练动作是**一次能做完的动作**（✓「把 T1、T3 的移项各重写一遍并逐项标号」），
> 复习计划是**按天/周排期**（✗「每天做 5 道，一周补上」）。脚本只抓排期措辞，别无他法。

### 4.3 前两道门的诚实边界

- `validate` 只查**形状**，`audit` 只查**措辞与引用**，**两者都不做数学判断**：
  "这三条模式是不是真的共享"只能靠人读出来。
- 证据门是**关键词匹配**，忽略个位数字；换个说法就可能误报或漏报，请人工过一眼。
- 措辞门抓固定说法，**换个说法绕过去它抓不住**；`W_GAP_MISMATCH` 也只是关键词匹配，
  换种措辞就可能误报，请人工过一眼。
- ★`case_count` 是**声明值**，脚本只能查"它是否比证据能对上的题数还大"（`E_CASE_COUNT_MISMATCH`），
  **查不出它是否真的由那些题支撑**。
- ★`cause.method` 是**声明值**：脚本无法验证同伴那次审查是否真的做过。
  `E_CAUSE_UNVERIFIED` 只保证"没有被声明为廉价核验"，不构成独立验证。
- `strength_kept` 是**强制项**，但脚本只能查"非空 + 不太短 + 不是模板话"，
  **查不出它是不是真的成立**——这一条只能人判。
- ★`W_LANGUAGE` 的立法范围**小于**上游：上游禁止"不贴粗心/基础差等标签",
  本表只把**卡片里对人不对事**算告警（本卡本来就允许"这批题里反复出现……"这种统计口径描述）。
  这条**不替代**上游的更强禁令。
- 通过前两道门只证明"卡片没越过这几条线"，**不证明归因在数学上成立**。

---

## 五、★第二段：举一反三 · 个性化定制题目

> 这一章是本次扩充的核心。**它不改第一段（归因）的任何立法**，
> 而是在归因完成之后**加一条显式授权的出题通道**。

### 5.1 合规性：同伴禁的是"未授权塞题"，不是"出题"

这是设计这一章前必须先解决的问题——上游两侧对"出题"的态度**看似矛盾**：

| 上游位置 | 原文 | 读法 |
| --- | --- | --- |
| `math-error-diagnosis/SKILL.md` 第 61 行 | 「**默认不另出练习**，不必重写整题」 | 默认模式不出题 |
| `math-error-diagnosis/SKILL.md` 第 66 行 | 「**只有用户请求时生成同类练习，先核验题目条件、解和完整性**，是否展示答案遵从用户要求」 | ★**允许出题**，三个前提 |
| `solution-refiner/SKILL.md` 第 36 行 | 「不出变式题、不排复习计划……」 | 在"优化正解"这一步禁止 |
| 上游 `AGENTS.md` | 「优化卡与诊断报告分开」 | 分层，不是禁止 |

**结论：同伴的立法不是"不许出题"，而是"不许未经请求就把题塞进诊断/优化交付物"。**
他给出了**三个前提**，本 skill 的出题门**逐条对应**，一条都不省：

| 同伴的前提 | error-atlas 的对应判据 |
| --- | --- |
| ① **只有用户请求时** | 触发条件（description）+ `practice_authorized` 授权标记 + `E_PRACTICE_UNAUTHORIZED` / `E_PRACTICE_MISSING` |
| ② **先核验题目条件、解和完整性** | ★**第三道门** `practice`（见 5.4），这是本次扩充最有分量的部分 |
| ③ **是否展示答案遵从用户要求** | `student_prompt` 与 `answer` / `solution_steps` **分离存放**，`E_ANSWER_IN_PROMPT` 抓泄漏 |

> 换句话说：**这一章不是绕过同伴的红线，而是走他亲手画出来的那条合法通道**，
> 并把他只写了一句的"核验条件、解和完整性"**做成了可执行的门**。

### 5.2 与通用出题器的分界（这才是"个性化"）

市面上的出题工具按**知识点**出题（"来 5 道圆锥曲线题"）。本 skill 按**你的错误模式**出题：

| | 通用出题器 | error-atlas 第二段 |
| --- | --- | --- |
| 出题依据 | 知识点 / 题型 / 难度 | ★**你做过错的那些模式**（`error_patterns`） |
| 绑定关系 | 无 | ★每题带 `pattern_ref`，指回 `error_patterns` 的序号 |
| 样本底线 | 无 | ★该模式 `case_count ≥ 2`（一道题错的模式**不准用来出题**） |
| 交付形态 | 题海 | ★恰好 5 题、三档难度、每个模式都被覆盖 |

**判据**：`validate` 强制每道题的 `pattern_ref` 指向**真实存在且 `case_count ≥ 2`** 的模式，
且每个模式**至少被一道题覆盖**。没有这条绑定，这个功能就退化成普通题库——
**绑定关系就是"个性化"的技术定义**。

### 5.3 第二段的字段

顶层新增三个字段（完整 schema 见 §二）：

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `practice_authorized` | bool | 授权标记：**无用户明确请求必须为 `false`**；为 `false` 时 `practice_items` 必须为空数组 |
| `practice_items` | object[] | **恰好 5 条**（授权时），每条七字段（见下） |
| `generation_basis` | string | 出题依据一句话：需点名**至少一个** `pattern` 名与**至少一个**题号 |

`practice_items` 每条恰好七个字段：

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `id` | string | 唯一，如 `P1` |
| `pattern_ref` | int | ★**必须是 `error_patterns` 的 1 基序号**，且该模式 `case_count ≥ 2` |
| `difficulty` | string | 三档之一：`同型巩固` / `变式迁移` / `综合拔高`；★5 题须**三档都出现** |
| `student_prompt` | string | ★**学生可见的题干**，只含条件与所求，**不含任何解法或答案** |
| `answer` | string | 标准答案（最终结果） |
| `solution_steps` | string | 关键解法步骤（简版，供家长/教师核验，不给学生） |
| `source_pattern` | string | 该题治的毛病，一句话（须与 `pattern_ref` 对应的 `pattern` 一致） |

### 5.4 ★第三道门：`practice --card card.json`（出题门 + 答案核验）

**这是本次扩充最有技术分量的一块**：它是本 skill 唯一**会做一次独立计算**的门。

调用签名：`error_card_check.py practice --card card.json [--verify-answers]`
退出码：`0` 通过 · `1` 出题不合格 · `2` 输入非法。

**A. 授权门（对应同伴前提①）**

| 码 | 级别 | 判据 |
| --- | --- | --- |
| `E_PRACTICE_UNAUTHORIZED` | error | `practice_authorized=false` 但 `practice_items` 非空；或 `practice_authorized` 缺失 / 不是 bool |
| `E_PRACTICE_MISSING` | error | `practice_authorized=true` 但 `practice_items` 为空（用户要了却没出题） |
| `W_NO_GENERATION_BASIS` | warning | `generation_basis` 没点到任何 `pattern` 名或任何题号 |

**B. 绑定门（对应"个性化"的技术定义）**

| 码 | 级别 | 判据 |
| --- | --- | --- |
| `E_PRACTICE_COUNT` | error | 不是**恰好 5 条** |
| `E_PRACTICE_ITEM_FIELDS` | error | 某条不是恰好七字段，或 `pattern_ref` 不是 int |
| `E_PATTERN_REF_RANGE` | error | `pattern_ref` 不在 `1..3`（指向不存在的模式） |
| `E_PATTERN_REF_THIN` | error | ★`pattern_ref` 指向的模式 `case_count < 2` —— **一道题错的模式不准出题** |
| `E_PATTERN_UNCOVERED` | error | ★有模式**一道题都没覆盖**——三块短板里漏了一块，等于没做个性化 |
| `E_SOURCE_MISMATCH` | error | `source_pattern` 与 `pattern_ref` 对应模式的 `pattern` 不一致 |
| `E_DIFFICULTY_UNKNOWN` | error | `difficulty` 不在三档内，或三档**没有全部出现** |
| `E_PRACTICE_DUP` | error | ★两题 `student_prompt` 去空白后**去重后不足 5 条**（出了重复题）；比结构不比数字，同型巩固档的数值变化不计为重复 |

**C. ★答案核验门（对应同伴前提②"核验题目条件、解和完整性"）**

`--verify-answers` 打开。**纯标准库实现**（`fractions` / `math` / 自写高斯消元），
只覆盖**可判定的小范围**，范围外明确 `skipped` 并计入 `--strict` 告警：

| 码 | 级别 | 判据 |
| --- | --- | --- |
| `E_ANSWER_MISSING` | error | `answer` 或 `solution_steps` 为空 |
| `E_ANSWER_IN_PROMPT` | error | ★`answer` 的实质内容出现在 `student_prompt` 里（**答案泄漏**，对应同伴前提③） |
| `E_ANSWER_UNRELATED` | error | ★`answer` 与 `student_prompt` **无任何共享数字或符号**——疑似答案与题对不上（仿关联度检查，忽略个位数字） |
| `E_ANSWER_LINEAR_UNSAT` | error | ★题干可解析为一元一次/二元一次方程（组）时，**代入 `answer` 不成立**。自写精确有理数高斯消元，**这是本门唯一会真正算一次的地方** |
| `E_ANSWER_DOMAIN_VIOLATION` | error | ★答案落在题干声明的定义域/范围之外（如题干写 `x>0`、答案给 `-2`；写 `x∈Z`、答案给分数） |
| `W_NO_SOLUTION_BASIS` | warning | 题干不是可解析算式（几何证明、应用题等）→ **明确跳过**，输出 `skipped: <原因>`，**不假装验过** |
| `W_ANSWER_NUMERIC_ONLY` | warning | 只有数值答案、无 `solution_steps` 支撑的题占比过半 |

> **口径（必须写进 SKILL.md）**：`E_ANSWER_LINEAR_UNSAT` 是**工具辅助核验**，
> **不是独立验证**——上游明确禁止"同一助手重做算独立验证"。
> 本门的诚实表述是：**"这一小类题，答案已用精确有理数运算代回验过；
> 其余题型只做了结构与关联检查。"**

### 5.5 两道门 → 三道门，三项产物

```
错题（≥2 道，各带同伴错因结论）
   ↓ 第一段
归因（error_patterns / capability_profile）
   ↓ validate 结构门 + audit 证据·引文门      ← 产物一：病理图
   ↓ 用户明确请求出题（授权门）
出题（practice_items，每题绑定一个模式）
   ↓ practice 出题门 + 答案核验门              ← 产物二：个性化练习（学生版无答案）
   ↓ 做完再错
交回同伴 math-error-diagnosis 诊断            ← 那两道新错题又成为下一轮的 `--cases` 输入
```

**闭环**：本 skill 的 `--cases` 输入来自同伴；本 skill 产出的练习题做完后判错，又回到同伴。
**这就是"错题归因整理 + 举一反三"的完整回路**——两段各有独立可验收的产物与门。

### 5.6 第二段的诚实边界

- `E_ANSWER_LINEAR_UNSAT` 只覆盖**可解析为线性方程/组**的题；范围外一律 `skipped`，
  **不假装验过**。二次方程、几何、证明、应用题都不在其中。
- ★**同一作者写出题器与答案验证器，存在循环依赖风险**（与上游"同一助手复核不能称为独立验证"同源）：
  即使脚本真的算了，**出题和验算用的是同一套符号约定与假设**。
  所以本门的表述严格限定为"工具辅助核验"。
- `E_DIFFICULTY_UNKNOWN` 只查三档**是否都出现**，**查不出难度标注是否名副其实**——
  "综合拔高"是否真的更难，只能人判。
- `E_PRACTICE_DUP` 只做**结构去重**（比文本骨架，不比数学等价），
  "两道不同的题其实考同一件事"这类**数学重复抓不住**。
- **出题的数学质量本身不受任何门保护**：三道门都过了，
  也只说明"题长得对、绑得对、一小类答案代回成立"。

---

## 六、成品 example（设计定位）

| 文件 | 场景 | 演示什么 |
| --- | --- | --- |
| `junior_three_cases.json` | 初中：3 道错题（去分母漏乘 / 移项变号 / 不检验根），未要求出题 | 正常通过；`practice_authorized=false`、`practice_items=[]` |
| `senior_four_cases.json` | 高中：4 道错题（判别式、定义域、分类讨论、前提检验），未要求出题 | 跨题共同点收敛到"前提检验缺位"；不含题目 |
| `practice_with_answers.json` | ★`senior_four_cases` 的**出题版** | 5 题三档、每题绑 `pattern_ref`；`practice --verify-answers` 通过并输出核验记录 |
| `bad_card.json` | 教具：结构合法但**越界** | `audit` 逐条驳回：自产错因 + 否定同伴结论 + 夹带题目 + 排复习计划 + 语气对人 |
| `bad_thin_card.json` | ★教具：结构合法但**证据不足** | `case_count=1` + `cause.method=numeric_only` + 指纹过期，演示**证据门**独立于越界门 |
| `bad_practice_card.json` | ★教具：归因合格但**出题不合格** | 有模式没被覆盖 + `pattern_ref` 指向 `case_count=1` 的模式 + 一题答案代回不成立，演示**第三道门** |

三份教具各演示**一道独立门**，这是这套设计的验收演示（仿你现有两件）：

- `bad_card.json`：`validate` 放行、`audit` 驳回 → **结构门管长得对不对，越界门管有没有跑到别人地盘**；
- `bad_thin_card.json`：一条越界措辞都没有，但样本量不足、核验方式廉价、指纹过期
  → 证明**证据门是独立的一道门**（上游把 `numeric_only` 明确排除在完整核验之外，这道门就是为它设的）；
- `bad_practice_card.json`：前两道门都放行，`practice` 退出码 1
  → 证明**出题门是第三道独立门**，不是归因的附属品。

---

## 七、验收标准（做完怎么算成功）

1. `error_card_check.py` 纯标准库、无依赖，四个子命令 `patterns`
   （打印**聚合维度表** + **同伴六类**两份菜单 + 从题面给关键词初判）/ `validate` / `audit` / ★`practice`；
2. 对上表每一个码，`example/` 里都有**至少一个真实触发它的实例**（一条码一份证据）；
3. `bad_card.json` 的 `validate` 退出码 0、`audit` 退出码 1；`bad_thin_card.json` 的 `validate` 退出码 0、
   `audit` 退出码 1 且**驳回理由全部来自证据门**；★`bad_practice_card.json` 的
   `validate`/`audit` 放行、`practice` 退出码 1；README 贴**真实输出原文**；
4. ★`practice --verify-answers` 必须真的跑出一次 `E_ANSWER_LINEAR_UNSAT` 的**实例**
   （一条入参 + 真实输出），否则不算做到"核验解"；
5. README 含五步法骨架：结构说明 + 快速体验 + **三道门分工表** + 诚实边界 + 给 agent 的安装/测试提示词；
6. ★README 必须写一节 **"与上游 `jrhhhh/math-homework-agent` 的关系"**：
   三条接口约定（`cause` 对象 / `method` 五值 / 指纹算法）+ 退出码语义对照表
   + **为何"出题"不违反上游禁令**（引 5.1 的两条原文）；
7. 落地后回头更新 `my_skill/README.md` 与 `solution_refiner/README.md` 的"分工"段，
   把四件作品串成一条链（**这条别忘：三份 README 现在互相只提两方**）；
8. ★新增本地 `AGENTS.md`（或项目 README 的"技能族与调度"一节），登记四个 skill 的选用条件
   与 error-atlas 的**两段准入前提**（≥2 道已修复错题 + 出题需用户明确请求）；
   **不去改同伴仓库的任何文件**。

---

## 八、下一步

设计稿定稿后，按此顺序落地（每步可独立验收）：

1. `error-atlas/SKILL.md` —— 五段骨架（Core Rules / 卡片格式 / Workflow / Output Standards /
   Prohibited Behavior + 能力边界），写清三条上游接口（`cause` 对象 / `method` 五值 / 指纹算法）
   与**两段式工作流**（归因 → 授权 → 出题）
2. `error-atlas/error_card_check.py` —— 按第四、五章判据清单实现四个子命令
   （结构门 19 条 + 证据/引文门 15 条 + ★出题门 11 条 + ★答案核验 7 条）
3. `error-atlas/example/` —— 三份正常卡（含出题版）+ 三份教具卡 + `cases.json`（带 `cause` 对象与指纹）
4. `error-atlas/README.md` —— 含真实运行输出、"与上游关系"一节（含 5.1 的禁令辨析）、
   给 agent 的冒烟测试提示词
5. 回改两份旧 README 的分工表 + 新增本地 `AGENTS.md`
