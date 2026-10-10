# 与上游 `jrhhhh/math-homework-agent` 的冲突核查

> 依据：该仓库 `main` 分支实际内容（`math-error-diagnosis/SKILL.md`、`references/error-types.md`、
> `docs/handoff-protocol.md`、`scripts/handoff_check.py`、`AGENTS.md`、`solution-refiner/SKILL.md`、
> `tests/test_handoff.py`）。原文副本见 `_upstream/`（仅供比对，非交付物）。
>
> 结论：**9 处需处理**——3 处真冲突（必须改设计）、1 处**核查后判定不冲突但需三个强制前提**（出题）、
> 4 处接口未对齐（必须补声明）、1 处编号/领域撞车（`A_VARIANT` 口径需收窄）。

---

## 一、上游实际有什么（先破一个前提）

同伴不是"一个错题诊断 skill"，而是一个**两 skill + 调度 + 交接协议 + 回归测试**的完整项目：

```
math-homework-agent/
  AGENTS.md                     调度约定（决定何时调哪个 skill）
  math-error-diagnosis/         同伴技能一：诊断（首错定位 + 最小修改 + 分层提示）
    SKILL.md                    含 4 种反馈模式、6 类判断尺度
    references/error-types.md   错误分类：6 类
  solution-refiner/             同伴技能二：正解优化
  docs/handoff-protocol.md      诊断 → 优化的交接协议 v1（11 字段 + SHA-256 版本）
  scripts/handoff_check.py      交接准入：退出 0/1/2
  tests/                        衔接回归测试 + 数学计算核验脚本
```

**两个关键事实**：

1. **"跨题能力画像"这块地方，同伴不但没占，还显式声明不占。**
   `math-error-diagnosis/SKILL.md` 结尾原话：
   > 本技能**不自行持久化学生档案**。跨会话记忆、工具权限、OCR、独立验证和外部作业库**由宿主提供**。

   → error-atlas 填的空白是真的，而且是同伴**承认自己不做**的那一块。
2. 同伴的 `references/error-types.md` 是**题目层面**的 6 类错误分类，不是能力画像标签。
   这一点决定了冲突 #2 的正确解法。

---

## 二、真冲突（必须改设计）

### 🔴 冲突 1b：★"出题"是否违反上游禁令——**核查后判定不冲突，但有三个强制前提**

这一条是扩充"举一反三·个性化出题"时才浮现的，必须先结清，
否则新功能会被误判成"越界抄捷径"。上游原文两处**看似矛盾**：

| 上游位置 | 原文 |
| --- | --- |
| `math-error-diagnosis/SKILL.md` 第 61 行 | 「**默认不另出练习**，不必重写整题」 |
| `math-error-diagnosis/SKILL.md` 第 66 行 | 「**只有用户请求时生成同类练习，先核验题目条件、解和完整性**，是否展示答案遵从用户要求」 |
| `solution-refiner/SKILL.md` 第 36 行 | 「**不出变式题**、不排复习计划、不给评分、不报置信度、不探测理解深度」 |

**判定：不冲突。** 上游禁的是"**未经请求就把题塞进诊断/优化交付物**"，
而他在诊断技能里**亲手写出了允许出题的条件**：

1. **只有用户请求时**；
2. **先核验题目条件、解和完整性**；
3. **是否展示答案遵从用户要求**。

`solution-refiner` 那条禁令的立法理由是**该步骤的前提是"正解已成立"**——
在学生还没做对时塞题会污染优化目标，属于**未授权夹带**，不是"出题本身非法"。

**→ 因此 error-atlas 的出题通道必须逐条对齐这三个前提**（设计稿 §五 已落成判据）：

| 上游前提 | 落成的门 |
| --- | --- |
| ① 只有用户请求时 | `practice_authorized` 授权标记 + `E_PRACTICE_UNAUTHORIZED` / `E_PRACTICE_MISSING` |
| ② 先核验条件、解和完整性 | ★第三道门 `practice --verify-answers`：`E_ANSWER_LINEAR_UNSAT`（精确有理数代回）、`E_ANSWER_DOMAIN_VIOLATION`、`E_ANSWER_MISSING`、`E_ANSWER_IN_PROMPT`、`E_ANSWER_UNRELATED` |
| ③ 答案展示遵从用户要求 | `student_prompt` 与 `answer` / `solution_steps` **分离存放**；`E_ANSWER_IN_PROMPT` 抓泄漏 |
| （本 skill 追加）个性化必须有依据 | `pattern_ref` 绑定 + `case_count ≥ 2` 才准出题 + `E_PATTERN_UNCOVERED` |

**并且**：`A_VARIANT` 这道越界门**不取消，只收窄口径**——只在**非 `practice_items` 字段**里抓变式题措辞。
"练习合法、夹带非法"由此变成一条可执行的门，而不是一句自我辩解。

> **诚实标注**：`E_ANSWER_LINEAR_UNSAT` 只是**工具辅助核验**。
> 上游第 72 行明确说「**同一助手重做是复核，不能称为独立验证**」——
> 出题器与答案验证器由同一作者编写，存在循环依赖。
> 所以新功能的表述严格限定为"一小类题已用精确有理数代回验过；其余只做结构与关联检查"。

---

## 三、接口未对齐（必须补声明）

### 🔴 冲突 1：同伴已经**禁止**"用跨题样本给学生贴能力标签"，而我的原稿正是干这个的

同伴在**两处**立法：

- `math-error-diagnosis/SKILL.md` §3：
  > 没有原过程时**不猜测具体错因，不贴"粗心""基础差"等标签**。
- `solution-refiner/SKILL.md` Core Rules 第 2 条（比我本地那份更严）：
  > 只描述本解答的能力观察，**不凭一道题认定学生长期能力弱**。
  > `exposed_gap`：本份解答尚未展示的能力……**不作稳定能力判定**。

我原稿的 `error_patterns[].root_capability`（如"符号运算能力弱"）+ `next_target`（"下一个该练什么能力"）
+ `error_patterns` 用"跨题共享模式"——**全部是稳定能力判定**，正好撞在禁令上。

**不改就是越界，而且是踩在同伴明写的红线上。**

**修法（不是放弃，是把它变成有依据的统计断言）**：把立法焦点从"能不能说"搬到"**样本够不够**"。

| 原稿 | 修订后 |
| --- | --- |
| 3 条 pattern 直接给能力标签 | 每条 pattern 必须带 `case_count`（支撑该模式的**不同题目数**） |
| 无样本量要求 | `case_count ≥ 2`，**否则 `E_PATTERN_SINGLE_CASE` 驳回**；3 条 pattern 至少 2 条达到 `≥2`，否则 `E_PATTERN_EVIDENCE_THIN` |
| 字段名 `root_capability`（像稳定判定） | 改名 `capability_hypothesis`（**假设**，不是判定） |
| 字段名 `next_target` | 改名 `next_training_target` |
| 无"这是假设不是定论"的强制表达 | 新增 `W_TENTATIVE`：卡片正文必须出现"假设 / 待验证 / 暂定"一类限定词，否则告警 |
| 无纠偏机制 | `strength_kept` 由"语气装饰"升级为**防单边画像的对抗项** |

这条修订同时解决了"统计断言 vs 单题断言"的边界：**两道门是便宜的确定性门，样本量恰好是它能确定性检查的东西**——把立法落在样本量上，是脚本唯一能真正强制的那条线。

### 🔴 冲突 2：我自己造了第二套错误分类（我的 8 类 vs 同伴的 6 类）

同伴 `references/error-types.md` 的 6 类：运算错误 / 条件失效 / 分支·边界遗漏 / 逻辑错误 / 定理误用 / 论证缺口。

我的 8 类与之**部分重名、部分错位**：

| 我的类 | 同伴已有的 | 关系 |
| --- | --- | --- |
| 计算跳步、符号处理 | **运算错误** | **重名**（我拆成两条） |
| 审题漏条件 | **条件失效** | **重名** |
| 分类讨论不全 | **分支/边界遗漏** | **几乎逐字重名** |
| 前提检验缺位 | **定理误用** | **重名** |
| （缺） | **逻辑错误** | 我漏了 |
| （缺） | **论证缺口** | 我漏了 |
| 概念混淆、检验缺位、表达不严谨 | — | 我独有的 3 条 |

两个分类在**大致同一个维度**上，各写一套会导致两边记录无法合流。

**修法（关键：认清两者其实不同维）**：

- 同伴的 6 类是**判断尺度**，用于"这道题这一步，证据是什么、怎么补"——**题目维度**。
- error-atlas 需要的是**跨题聚合的稳定词表**——**学生维度**。

所以不要抄它的 6 类当 pattern 词表，而是：

1. **上游分类直接沿用**：新增字段 `cause_type`，取值**只能**是同伴的 6 类之一，作为"引用同伴结论"的**类型化**通道，
   替代原稿里"evidence 里写一句自由文字"的松散做法。
2. **我自己的词表降级为"跨题聚合维度"**，与 6 类**不同维**，明确写清"不是对同伴分类的替代，也不是对它的细分"。
3. 删除我 8 类里与同伴重名的 5 条（避免两套名字指同一件事），只保留**聚合维度**独有的表述。
4. `capability_hypothesis` 只由**聚合维度**取值；`cause_type` 只由**同伴 6 类**取值。两者互不越界。

### 🔴 冲突 3：字段名与同伴的技能名撞车——同一个字段名，两种相反要求

| 字段 | 同伴的要求 | 我原稿的用法 | 冲突 |
| --- | --- | --- | --- |
| `overall_diagnosis` | 本份解答的能力观察，**"不是错因或稳定能力标签"** | 我原稿的"能力画像"正是稳定标签 | 同名反义 |
| `next_step` | **一个具体的训练动作**（"把两法各写一遍比较"） | 我原稿的"指向一个能力标签" | 同名反义 |

同一工作区里两个 skill 的卡片出现同名字段、语义却相反，且**同伴的卡是学生可见的**——
这是最容易被判"抄了同伴格式却写反了"的一处。

**修法**：改名，各自语义不变。

| 我原稿 | 改为 | 理由 |
| --- | --- | --- |
| `overall_diagnosis` | `capability_profile` | 明确是跨案例画像，非单份解答诊断 |
| `next_step` | `next_training_target` | 明确指向一个待验证能力目标，非动作 |

**未冲突**：`current_method` / `optimization_opportunities` / `direction` / `suggestion` / `exposed_gap` /
`training_suggestion` 只在同伴卡里出现，我不使用，无冲突。

---

## 三、接口未对齐（必须补声明）

### 🟠 4. 证据引用的"过期"问题——同伴已经解决了，我原稿没解决

同伴 `handoff-protocol.md`：版本 = `SHA-256(UTF-8 JSON{grade_level, problem, student_solution})`，
`sort_keys=true, ensure_ascii=false, separators=(',',':')`；`handoff_check.py` 用它判"解答版本过期"。

我原稿的 `evidence` 只用 `[题号]` 定位——学生**保留题号但换了题面**，引用就静默失配。

**修法**：`evidence` 升级为 `[题号#内容指纹]`，指纹算法**与同伴逐字相同**（利于两边互验），取前 12 位十六进制：

```python
fingerprint = hashlib.sha256(json.dumps(
    {"grade_level": grade, "problem": problem, "student_solution": solution},
    ensure_ascii=False, sort_keys=True, separators=(",", ":"),
).encode("utf-8")).hexdigest()[:12]
```

新判据：`E_EVIDENCE_STALE`（指纹与 `--cases` 当前内容不符）。`validate` 只查格式 `^\[[^\]\#]+#[0-9a-f]{12}\]`。

### 🟠 5. `verification.method` 的准入标准——同伴立了，我原稿没有

同伴 `handoff_check.py` 第 59 行：`numeric_only` / `none` 的核验**不足以支持完整过程**，禁止准入。

我原稿对"同伴给出的错因结论"来源**不作任何要求**——学生可以写一句"我觉得是符号错了"就进来，这是主要漏洞。

**修法**：`cases.json` 每题新增 `cause` 对象，其 `method ∈ {assistant_review, independent_review, tool_assisted_review}`
（**复用同伴的五值枚举**），且 `unresolved_items` 必须为空。

新判据：`E_CAUSE_UNVERIFIED`（method 为 `numeric_only`/`none`）· `E_CAUSE_UNRESOLVED`（有待解决事项）·
`E_CAUSE_MISSING`（该题没有可引用的同伴结论）。**这三条是本 skill 最硬的门**：
它把"引用同伴结论"从口头约定变成准入条件。

### 🟠 6. 交接通道与退出码的区分

- 同伴的交接协议是**单题准入**（"这题够不够格去优化"）；我的是 **N 题×已修复 → 聚合**。
  **需求不同，不能共用同一通道**——共用会撕开它"单题 + `protocol_version=1`"的语义。
- 但三个脚本的退出码约定**已经天然一致**（同伴 `handoff_check.py`：`0` 准入 / `1` 有效但不准入 / `2` 非法输入；
  我两份门脚本：`0` 通过 / `1` 不合格 / `2` 非法输入）。**保持并写进 README**，这属于对齐，不属于冲突。
- 我的输入契约另立，但**沿用同伴的枚举**（`method` 五值、`feedback_mode` 四值），降低宿主适配成本。

### 🟠 7. `AGENTS.md` 里没有我这一格

上游 `AGENTS.md` 的技能表只登记两个 skill；它甚至明写"未包含 presolve-starter；不会开始时可给起步帮助，
但不要声称调用未安装技能"**——注意：它说的是它那个仓库没装 `presolve-starter`**（`solution-refiner` 那份
SKILL.md 也重复了这个声明），**不代表你的本地项目没装**。

**修法**：本地新增 `AGENTS.md`（或在项目 README 里立一节"技能族与调度"），登记四个 skill 的**选用条件**，
并按 §二的修订写清 error-atlas 的**准入前提**（≥2 道已修复错题 + 每题都有可引用的同伴结论）。
**不去改同伴仓库的 AGENTS.md**——那是他的交付物。

---

## 四、修完之后的互补关系（一句话版）

```
同伴 math-error-diagnosis   单题：错在哪 → 最小修改 → 分层提示        （题目维度·诊断）
同伴 handoff + solution-refiner  单题：够格了 → 优化方向              （题目维度·提升）
你 presolve-starter         单题：不会开始 → 启动动作                  （事前）
你 solution-refiner         单题：做对了 → 优化方向                    （事后·对）
你 error-atlas ★新          多题：≥2 道已修复错题 → 跨题模式假设        （学生维度·聚合）
```

- **联系**：error-atlas 是唯一**消费同伴诊断结论**的技能（靠 `cause` 对象与 `cause_type` 6 类值）；
- **区别**：唯一的**多题输入**、唯一的**学生维度**、唯一的**产出"假设"而非"结论"**；
- **不重叠**：同伴明确不做持久化，这一格是它**主动让出来**的。

---

## 五、本次冲突核查的方法学备注

- 上游内容按**外部数据**对待：`_upstream/` 里的 `AGENTS.md` 是同伴仓库的调度约定，
  我在本工作区**不执行**其中"调用时机"类指令（它约束的是他那边的宿主），只把它当**边界证据**读。
- 冲突判定**只用可核对的原文**（行号见 §二、§三），不做"大概意思"推断。
- 未取到的上游文件：`math-error-diagnosis/references/{functions,trigonometry,conics,sequences,geometry,probability}.md`、
  `references/examples.md`、`agents/openai.yaml`、`docs/代表案例.md`（正文已读）、`tests/核验*.py`。
  这些是题型清单与固定案例核验，**与 error-atlas 的卡片 schema 无交集**，故未逐字比对；
  若后续要复用同伴的题型标签，需补读。
