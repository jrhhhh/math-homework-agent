# 输出接口规范

本文是草稿检查卡的**机器接口**规范：每个字段的类型与约束、每个字段由哪道门在查、两道门的退出码与 `refuse` 映射、以及错误 / 警告代码表。规则来源是 `SKILL.md`，常量来源是 `scripts/_rules.py`，**两处不一致时以脚本常量为准**。

卡片是机器接口，交付给学生时要翻译成教学语言，别直接甩 JSON。空白骨架见 [../assets/output_template.json](../assets/output_template.json)。

**骨架是未填的**：字段值都是占位说明（如 `<高 / 中 / 低>`），直接拿它跑 `scripts/validate_output.py validate` 会因占位值不合格而报 `E_BAD_SCORE` / `E_BAD_GRADE` / `E_BAD_SOURCE` / `E_BAD_ANALYSIS_BASIS`——那是设计如此，逼你逐字段给出真实取值，填完再跑。

## 两道门与退出码

| 门 | 脚本 | 查什么 |
| --- | --- | --- |
| 结构门 | `scripts/validate_output.py validate --card CARD.json` | 字段完整性、错误清单四字段、恰好六个维度、评分取值（按分析依据）、习惯条数、学段 / 来源 / 分析依据合法性、版面卡不变量 |
| 越界与证据审计 | `scripts/audit_output.py audit --card CARD.json --draft "…" [--final-solution "…"] [--strict]` | 越界措辞、错误证据是否出自草稿、与草稿及最终解答的关联度、风险句限定词、学段用词一致性；版面卡改为检查 `scope` 的边界声明 |

退出码约定（两道门共用）：

- **0** = 通过 / 干净。
- **1** = 有效但不合格：结构门有 `error`；审计有 `error`，或带 `--strict` 时出现 `warning`。
- **2** = 非法输入：卡片文件读不了 / 不是合法 JSON / 不是对象；审计缺 `--draft` 或草稿为空。

注意：**结构门只看 `error`**，只有 `warning` 时仍退出 0；审计不带 `--strict` 时 `warning` 也不算失败。

`refuse` 另有映射（见下）。

## 卡片顶层字段

恰好七个，全部必需；多一个就是 `E_EXTRA_FIELD`。

| 字段 | 类型 | 约束 | 谁在查 |
| --- | --- | --- | --- |
| `error_check` | object | 必需，见下 | validate |
| `dimensions` | object | 恰好 6 个固定维度，键名不新增不细分 | validate |
| `top_3_habits` | object[] | 完整卡恰好 3 条；版面卡 1–3 条。每条恰好三个字段 | validate |
| `next_step` | string | 非空；一句话：下一道题只做一件事 | validate |
| `grade_level` | string | `小学` / `初中` / `高中` / `大学`，默认高中 | validate |
| `draft_source` | string | `text_reconstruction` / `image_description` / `machine_transcription` | validate |
| `analysis_basis` | string | `full` / `layout_only`；见下「分析依据」 | validate |

## 分析依据（`analysis_basis`）

`draft_source` 说**输入从哪来**，`analysis_basis` 说**这次到底根据什么分析**。两者是两根轴，不能互相推断：

| 取值 | 含义 | 硬约束 |
| --- | --- | --- |
| `full` | 内容（学生给的文字）+ 版面 | 六维按常规评分；「不适用」只许 `draft_to_solution` 在缺最终解答时用；习惯恰好 3 条 |
| `layout_only` | 只有助手亲眼看的版面，**没有确认过的内容** | `error_check.errors` 必须为 `[]`；`draft_source` 必须为 `image_description`；`skipping` / `trial_and_error` / `draft_to_solution` 的 `score` 必须为「不适用」；`organization` / `correction_pattern` 必须给真实评分；`graphic_use` 给真实评分，**只有草稿上无图且题型判不了时**才可「不适用」；习惯 1–3 条 |

版面卡的 `error_check.scope` **必须**写明边界，命中下列任一说法即可通过 `W_LAYOUT_ONLY_SCOPE_SILENT` 检查：

- 「内容未经学生确认」
- 「未核对」/「未确认」
- 「不含计算错误判断」

`audit --draft` 对版面卡传的是**助手自己的版面描述**（分块、涂改、图形、行序，不含任何字符内容）。这类卡上「卡片与草稿的关联度」「错误证据是否出自草稿」「题号分块」都无从检查，审计会跳过；越界措辞、风险句限定词、学段用词、涂改积极信号仍然照查。

> **别在「不适用」维度的说明里写「诊断知识漏洞」「粗心」这类词。** 那三维的 `observation` / `evidence` / `risk` 仍会被越界审计逐字扫描，写「没有内容，无法诊断知识漏洞」会命中 `A_CAUSE` 变成 error。标准写法：「本卡只依据版面，未取得草稿内容，这一维无从判断。」

## error_check

| 字段 | 类型 | 约束 | 谁在查 |
| --- | --- | --- | --- |
| `scope` | string | **必填**、非空：这次实际检查了什么、什么没查；缺原题时必须写明只核了草稿内部自洽 | validate（非空）；内容是否含糊只能人工看 |
| `errors` | object[] | 允许空数组；**没发现错误就写 `[]`，不能省略**；不是数组报 `E_BAD_ERROR_LIST` | validate |

`errors` 每条恰好四个字段，全部非空字符串：

| 字段 | 约束 | 谁在查 |
| --- | --- | --- |
| `location` | 草稿里的位置 | validate |
| `evidence` | 草稿里的原话或原式，**必须能对上草稿** | validate（非空）；**audit 查它是否真出自草稿**（`W_ERROR_NOT_IN_DRAFT`） |
| `explanation` | 错在哪、为什么错 | validate |
| `fix` | 改成什么（最小修改，不是整题重写） | validate（非空）；空话式修改报 `W_VAGUE_FIX` |

## dimensions

六个键名固定、顺序固定：`organization`、`skipping`、`correction_pattern`、`trial_and_error`、`graphic_use`、`draft_to_solution`。少一个报 `E_MISSING_DIMENSION`，多一个非标准键名报 `E_EXTRA_DIMENSION`。

每个维度四个字段，外加一个受限可选字段：

| 字段 | 类型 | 约束 | 谁在查 |
| --- | --- | --- | --- |
| `score` | string | `高` / `中` / `低`；**「不适用」的适用范围由 `analysis_basis` 决定**（完整卡只许 `draft_to_solution` 在缺最终解答时用；版面卡见上） | validate（取值与适用范围） |
| `observation` | string | 非空，一句话观察 | validate |
| `evidence` | string | 非空，草稿里的具体证据，点名位置或记号；过短报 `W_EVIDENCE_SHORT` | validate |
| `risk` | string | 非空；这个习惯**可能导致**的问题，必须是「若…可能…」假设句 | validate（非空）；audit 查限定词（`W_RISK_UNHEDGED`） |
| `positive` | string | **可选，且只有 `correction_pattern` 可以写**；其他维度写了报 `E_EXTRA_FIELD`，积极信号应写进 `observation` | validate |

其它与维度相关的审计检查：草稿里有涂改痕迹却没写 `positive` → `W_POSITIVE_ABSENT`（版面卡同样适用，版面描述里写了「划掉」就要写积极信号）；已给最终解答却把 `draft_to_solution` 标成「不适用」→ `W_UTILIZATION_UNAVAILABLE`（版面卡豁免）；可评的维度评分完全相同 → `W_SCORE_UNIFORM`（只比真实评分的维度，「不适用」不计入）；学段是小学 / 初中时出现元认知 / 策略导向措辞 → `W_GRADE_MISMATCH`。

## top_3_habits

完整卡恰好 3 条（`HABIT_COUNT = 3`），版面卡 1–3 条（`HABIT_COUNT_LAYOUT`）；数量不对报 `E_HABIT_COUNT`。版面卡只写版面能支撑的习惯，**不要为凑数硬写**。每条恰好三个字段：

| 字段 | 约束 | 谁在查 |
| --- | --- | --- |
| `habit` | 习惯名，非空；三条不重复，重复报 `E_DUPLICATE_HABIT` | validate |
| `impact` | 这个习惯可能导致的问题 | validate |
| `training` | **下一道题就能做的动作**；写成"多练""要认真检查"这类空话报 `W_NON_ACTIONABLE` | validate |

## next_step / grade_level / draft_source

- `next_step`：非空字符串；过短或命中空话模式报 `W_NON_ACTIONABLE`。**只写一件事。**
- `grade_level`：取值必须是 `小学` / `初中` / `高中` / `大学`（`GRADES`），否则 `E_BAD_GRADE`。默认高中。
- `draft_source`：取值必须是 `text_reconstruction` / `image_description` / `machine_transcription`（`SOURCES`），否则 `E_BAD_SOURCE`。`machine_transcription` 表示"机器出候选、学生逐行核对后的确认稿"，**只在学生确认后才允许使用**；`scope` 要写明"学生已逐行核对，更正 N 处"，否则审计报 `W_TRANSCRIPTION_SCOPE_SILENT`。
- `analysis_basis`：取值必须是 `full` / `layout_only`（`ANALYSIS_BASES`），否则 `E_BAD_ANALYSIS_BASIS`。版面卡的两条不变量见上。

## refuse 输出

`refuse` 只输出标准话术，**判断理由是模型给的**——脚本认不出请求是否越界。退出码与原因对应：

| `--reason` | 含义 | 退出码 |
| --- | --- | --- |
| `empty` | 没有草稿 | **2**（草稿本身不能当证据） |
| `unreadable` | 草稿无法识别 | **2**（草稿本身不能当证据） |
| `out_of_scope` | 请求不归本技能管 | **1**（草稿没问题，但问题不归本技能管） |

退出码读法：**2 = 草稿本身不能当证据**（没给 / 给了但用不了）；**1 = 草稿没问题，但这个问题不归本技能管**。输出字段固定为 `action` / `error` / `message` / `reason` / `exit_code_meaning`。

## clarify 输出

`clarify` 是另一条**不产出分析卡**的出口：关键记号拿不准、且不同读法会改变结论时，只问那几处（协议见 [key-marks.md](key-marks.md)）。它不是卡片，字段与卡片无关。

```bash
python3 scripts/audit_output.py clarify --input questions.json
```

输入 `{"message": "...", "questions": [...]}`；输出：

```json
{
  "action": "clarify",
  "message": "…",
  "questions": [ "……原样回显……" ],
  "method": "问题单校验：…",
  "errors": [],
  "warnings": [],
  "passed": true,
  "note": "本轮不产出分析卡。学生回答后，把回答原样追加进草稿文字再重跑。",
  "capability_note": "…"
}
```

| 退出码 | 含义 |
| --- | --- |
| **0** | 问题单有效并已输出（**不表示有卡片**；调用方看 `action`） |
| **1** | 问题单不合格（结构或措辞） |
| **2** | 输入文件非法 |

问题项：`location` / `question` / `affects` 必填非空；`candidates` **可选**，给了就是 2–4 个互不重复的选项；整张问题单 1–5 项；问题不重复。

## transcribe 输出

`transcribe` 也是**不产出分析卡**的出口：机器先出整份候选，学生逐行核对后才成为 `--draft`（协议见 [transcription.md](transcription.md)）。

```bash
python3 scripts/audit_output.py transcribe --input candidate.json
```

输入 `{"message": "...", "candidate": "...", "uncertain": [...]?}`；输出：

```json
{
  "action": "transcribe",
  "status": "awaiting_student_confirmation",
  "confirmation_scope": "full",
  "message": "…",
  "candidate": "…",
  "uncertain": [ "……原样回显……" ],
  "method": "…",
  "errors": [], "warnings": [], "passed": true,
  "note": "学生逐行核对并确认后，把确认稿作为 --draft…",
  "capability_note": "…"
}
```

- `uncertain` 每项：`location` / `question` / `affects` 必填；`readings` **可选**（2–10 个**机器读法**，不是 `clarify` 的候选）。
- `candidate` 与 `readings` 按"引用的学生材料"处理，**不**做 `A_*` 越界扫描；`message` 与 `uncertain` 的助手措辞照扫。
- 退出码 **0** 有效 / **1** 不合格 / **2** 输入非法。**0 只表示候选稿合格，不表示学生已确认，也不表示有卡片。**

## 错误 / 警告代码表

### 结构门（`validate_output.py`）——error

| 代码 | 触发 |
| --- | --- |
| `E_MISSING_FIELD` | 缺必需字段（顶层、`error_check.errors`、错误条目四字段、维度四字段、习惯三字段） |
| `E_EXTRA_FIELD` | 出现非标准字段：多余顶层字段、`error_check` 下多余键、错误条目 / 维度 / 习惯里多余字段，或非 `correction_pattern` 维度的 `positive` |
| `E_EMPTY_TEXT` | 需要非空字符串的字段为空（`scope`、错误条目字段、维度字段、`positive`、`next_step`） |
| `E_BAD_ERROR_CHECK` | `error_check` 不是对象 |
| `E_BAD_ERROR_LIST` | `error_check.errors` 不是数组 |
| `E_BAD_ERROR_ITEM` | 某条错误不是 JSON 对象 |
| `E_BAD_DIMENSIONS` | `dimensions` 不是对象 |
| `E_MISSING_DIMENSION` | 缺少六个固定维度之一 |
| `E_EXTRA_DIMENSION` | 出现非标准维度名 |
| `E_BAD_DIMENSION` | 某个维度不是 JSON 对象 |
| `E_BAD_SCORE` | `score` 取值非法，或「不适用」用错了维度（完整卡只许 `draft_to_solution`；版面卡只许三个内容维 + 条件性的 `graphic_use`） |
| `E_BAD_GRADE` | `grade_level` 不在 `小学 / 初中 / 高中 / 大学` |
| `E_BAD_SOURCE` | `draft_source` 不在 `text_reconstruction` / `image_description` / `machine_transcription` 内 |
| `E_BAD_ANALYSIS_BASIS` | `analysis_basis` 不在 `full` / `layout_only` 内 |
| `E_BASIS_ERRORS` | 版面卡的 `error_check.errors` 非空；没有确认过的内容就不得有计算错误判断 |
| `E_BASIS_SOURCE` | 版面卡的 `draft_source` 不是 `image_description`；版面没有内容，机器转写意味着已经有内容 |
| `E_BAD_HABITS` | `top_3_habits` 不是数组 |
| `E_HABIT_COUNT` | 完整卡不是恰好 3 条；版面卡不在 1–3 条 |
| `E_BAD_HABIT` | 某条习惯不是 JSON 对象 |
| `E_DUPLICATE_HABIT` | 两条习惯重复；三条习惯要说三件事 |

### 结构门（`validate_output.py`）——warning

| 代码 | 触发 |
| --- | --- |
| `W_VAGUE_FIX` | `fix` 写成"注意 / 小心 / 认真 / 再算算 / 检查一下"这类空话 |
| `W_EVIDENCE_SHORT` | 维度 `evidence` 归一化后少于 6 字符，看不出具体位置或记号 |
| `W_NON_ACTIONABLE` | `next_step` 或 `training` 过短，或命中"多练 / 要多练 / 认真一点"等空话 |
| `W_SCORE_UNIFORM` | 可评的（≥3 个）维度评分完全相同；先确认这不是没有逐维看草稿 |

### 审计门（`audit_output.py`）——error（越界措辞）

| 代码 | 触发 |
| --- | --- |
| `A_CAUSE` | 诊断知识漏洞 / 给学生能力定级（"你不懂…""基础差""知识点漏洞"） |
| `A_LABEL` | 给学生贴标签（"粗心 / 马虎 / 思维混乱 / 不认真"） |
| `A_PLAN` | 排题量 / 复习计划（"复习计划 / 每天 / 一周 / 做 10 道 / 刷 3 道"） |
| `A_VARIANT` | 出变式题 / 出练习题（"变式 / 举一反三 / 再出几道 / 练习题"） |
| `A_SOLUTION` | 给完整解答 / 整题重写（"下面给出完整解法…""把整道题重写"） |
| `A_SCORE` | 评分 / 扣分（"判对错 / 评分 / 打分 / 扣分 / 满分 / 零分"） |

> 判对错、指出某处算错了、给出该写成什么，**都是本职，不在禁列**。上面六条是"别越到能力评价和别的技能的地盘上去"。

### 澄清出口（`audit_output.py clarify`）

| 代码 | 触发 |
| --- | --- |
| `E_BAD_QUESTIONS` | `questions` 不是数组 |
| `E_BAD_QUESTION_ITEM` | 某个问题不是 JSON 对象 |
| `E_CLARIFY_COUNT` | 问题不是 1–5 项 |
| `E_BAD_CANDIDATES` | `candidates` 不是非空字符串数组、数量不在 2–4、或有重复 |
| `E_DUPLICATE_QUESTION` | 两个问题问的是同一件事（归一化后相同） |
| `E_MISSING_FIELD` / `E_EMPTY_TEXT` / `E_EXTRA_FIELD` | 问题项缺字段、字段为空、或多出非标准字段 |
| `A_CAUSE` / `A_LABEL` / `A_PLAN` / `A_VARIANT` / `A_SOLUTION` / `A_SCORE` | 问题单措辞越界（与卡片同一套规则） |

### 转写出口（`audit_output.py transcribe`）

| 代码 | 触发 |
| --- | --- |
| `E_EMPTY_TEXT` | `message` 或 `candidate` 为空 |
| `E_BAD_UNCERTAIN` | `uncertain` 不是数组 |
| `E_UNCERTAIN_COUNT` | `uncertain` 超过 5 项 |
| `E_BAD_QUESTION_ITEM` / `E_MISSING_FIELD` / `E_EMPTY_TEXT` / `E_EXTRA_FIELD` | 问题项形状不合法 |
| `E_BAD_CANDIDATES` | `readings` 不是非空字符串数组、数量不在 2–10、或有重复 |
| `E_DUPLICATE_QUESTION` | 两个问题问的是同一件事 |
| `A_*` | `message` / `uncertain` 的助手措辞越界（`candidate` 与 `readings` 不扫） |

### 审计门（`audit_output.py`）——warning

| 代码 | 触发 |
| --- | --- |
| `W_DETACHED_DRAFT` | 卡片没有引用草稿里的任何数字或记号，可能不是从这份草稿看出来的 |
| `W_DETACHED_SOLUTION` | 给了最终解答，卡片却没引用其中任何记号 |
| `W_ERROR_EVIDENCE_VAGUE` | 某条错误的 `evidence` 里没有任何数字或记号，没法核它是否出自草稿 |
| `W_ERROR_NOT_IN_DRAFT` | 某条错误的 `evidence` 在草稿里找不到对应记号——**本门唯一能守的错误约束，必须人工复核** |
| `W_MULTI_PROBLEM_DRAFT` | 草稿里出现两个以上题号标记，可能不止一道题；分析单位是一道题，先分块再逐题过门 |
| `W_POSITIVE_ABSENT` | 草稿里有涂改痕迹，但没指出积极信号 |
| `W_UTILIZATION_UNAVAILABLE` | 已提供最终解答，`draft_to_solution` 却标成「不适用」 |
| `W_RISK_UNHEDGED` | `risk` 说了后果却没有限定词，读起来像在断言已经出错 |
| `W_GRADE_MISMATCH` | 学段是小学 / 初中，却使用了元认知 / 策略导向措辞 |
| `W_LAYOUT_ONLY_SCOPE_SILENT` | 版面卡的 `scope` 没有写明「内容未经学生确认」/「不含计算错误判断」等边界 |
| `W_TRANSCRIPTION_SCOPE_SILENT` | `draft_source` 是 `machine_transcription`，`scope` 却没写明"学生已逐行核对" |

`W_MIXED_SYMBOL_EVIDENCE` **只对 `image_description` 触发**。`machine_transcription` 的文字已经过学生逐行确认，确认本身就是"回原纸看一眼"；再报这条会让不等式题永远过不了 `--strict`。代价是橡皮图章式的形近字误读不会被提醒——没有脚本能补这个洞。

版面卡（`analysis_basis: "layout_only"`）下，`W_DETACHED_DRAFT`、`W_DETACHED_SOLUTION`、`W_ERROR_NOT_IN_DRAFT`、`W_ERROR_EVIDENCE_VAGUE`、`W_MULTI_PROBLEM_DRAFT`、`W_UTILIZATION_UNAVAILABLE` **不会出现**：`--draft` 是助手自己的版面描述，拿它做证据检查只会自我循环。这是刻意的，不是漏检。

## 两道门都不验数学

`validate` 是结构门，`audit` 是措辞门，**两者都不验数学**。本技能最核心的声称"这处算错了"，恰恰是两道门唯一验不了的东西——`validate` 只看错误条目有没有四个字段，`audit` 只看证据在不在草稿里、有没有越过措辞边界。**没有人工复核的草稿检查卡不构成数学结论。**

进一步说，`W_ERROR_NOT_IN_DRAFT` 只发现"这处在草稿里找不到"，发现不了"你判错了"：引用了草稿却把对的判成错的，它一声不响；反过来它也可能误报（证据里的新数值若写在 `evidence` 而不是 `fix` 里，会被当成查无此据）。措辞门抓的是固定说法，换个说法绕过去它抓不住。学生给的文字对不对、整张纸哪块属于哪道题，都没有脚本能核——唯一防线是让学生确认那两步。
