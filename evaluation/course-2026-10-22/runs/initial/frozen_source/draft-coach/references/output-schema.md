# 输出 Schema 与门脚本

本文是 [`SKILL.md`](../SKILL.md) `Output Format` 的逐字段说明。**规则以 `SKILL.md` 为准**；
字段常量、越界正则、学段表以 [`scripts/_rules.py`](../scripts/_rules.py) 为准。

两道门：

| 门 | 命令 | 查什么 |
| --- | --- | --- |
| 结构门 | `scripts/validate_output.py validate --card CARD.json` | 字段完整性、六个维度、评分取值、1–3 条习惯、学段与来源 |
| 越界审计 | `scripts/audit_output.py audit --card CARD.json --draft "…" [--strict]` | 越界措辞、风险句限定词、学段用词、整张纸多题提示 |

退出码：**0** 通过 / 干净 · **1** 有效但不合格（有 error，或 `--strict` 下出现 warning） · **2** 输入非法。

## 卡片顶层字段

恰好六个，全部必需；多一个就是 `E_EXTRA_FIELD`。

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `scope` | string | **必填**、非空：这次看了什么、没看什么（只看版面、未读字符、缺原题等） |
| `dimensions` | object | 恰好 6 个固定维度，键名不新增不细分 |
| `top_3_habits` | object[] | 1–3 条，每条恰好三个字段 |
| `next_step` | string | 非空；一句话：下一道题只做一件事 |
| `grade_level` | string | `小学` / `初中` / `高中` / `大学`，默认高中 |
| `draft_source` | string | `text_reconstruction` / `image_description` |

## dimensions

六个键名固定、顺序固定：

| 键名 | 中文 | 看什么 |
| --- | --- | --- |
| `organization` | 分区与边距 | 题号/分块、已知/求/推导是否分开；多题是否混写 |
| `skipping` | 步骤分行与密度 | 高风险步骤（移项/去括号/开方/分类边界/代入）是否单独落行 |
| `correction_pattern` | 划改与自纠 | 划改位置、旧值是否明确作废、有没有补写 |
| `trial_and_error` | 多路径标记 | 分类讨论/多解/多方法有没有标号或箭头区分 |
| `graphic_use` | 图形与标注 | 几何图顶点/辅助线/交点、函数图坐标轴/极值点是否标注 |
| `draft_to_solution` | 留白与检验区 | 有没有检验区，答句/单位/范围有没有固定落点 |

**草稿不是答卷：** 允许简写、箭头、缩写、低风险步骤心算；评分看的是「可追溯、可复核、可区分」，不是工整、不是每步都写、也不是涂改越少越好。

每个维度四个字段，外加一个受限可选字段：

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `score` | string | `高` / `中` / `低` / `不适用`；标「不适用」时 `observation` 必须写明原因 |
| `observation` | string | 非空，一句话观察 |
| `evidence` | string | 非空，版面里的具体位置或痕迹；过短报 `W_EVIDENCE_SHORT` |
| `risk` | string | 非空；必须是「若…可能…」的假设句，否则报 `W_RISK_UNHEDGED` |
| `positive` | string | **可选，且只有 `correction_pattern` 可以写**；其他维度写了报 `E_EXTRA_FIELD` |

其它检查：草稿里有划改痕迹却没写 `positive` → `W_POSITIVE_ABSENT`；六个维度评分完全相同 → `W_SCORE_UNIFORM`；六个维度全部「不适用」→ `W_ALL_UNAVAILABLE`；学段是小学/初中时出现元认知/策略导向措辞 → `W_GRADE_MISMATCH`。

## top_3_habits

1–3 条；每条恰好三个字段：

| 字段 | 约束 |
| --- | --- |
| `habit` | 习惯名，非空；同一张卡里不重复，重复报 `E_DUPLICATE_HABIT` |
| `impact` | 这个习惯可能导致的问题 |
| `training` | **下一道题就能做的动作**；写成"多练""要认真检查"这类空话报 `W_NON_ACTIONABLE` |

## next_step / grade_level / draft_source

- `next_step`：非空字符串；过短或命中空话模式报 `W_NON_ACTIONABLE`。**只写一件事。**
- `grade_level`：四个取值之一。
- `draft_source`：两个取值之一。

## 错误 / 警告代码表

### 结构门——error

| 代码 | 触发 |
| --- | --- |
| `E_MISSING_FIELD` | 缺必需字段（顶层、维度四字段、习惯三字段） |
| `E_EXTRA_FIELD` | 多余顶层字段、维度/习惯里多余字段、非 `correction_pattern` 维度的 `positive` |
| `E_EMPTY_TEXT` | 需要非空字符串的字段为空（`scope`、维度字段、`positive`、`next_step`） |
| `E_BAD_DIMENSIONS` | `dimensions` 不是对象 |
| `E_MISSING_DIMENSION` | 缺少六个固定维度之一 |
| `E_EXTRA_DIMENSION` | 出现非标准维度名 |
| `E_BAD_DIMENSION` | 某个维度不是 JSON 对象 |
| `E_BAD_SCORE` | `score` 不在 `高 / 中 / 低 / 不适用` 内 |
| `E_BAD_GRADE` | `grade_level` 不在四个取值内 |
| `E_BAD_SOURCE` | `draft_source` 不在两个取值内 |
| `E_BAD_HABITS` | `top_3_habits` 不是数组 |
| `E_HABIT_COUNT` | 习惯不在 1–3 条内 |
| `E_BAD_HABIT` | 某条习惯不是 JSON 对象 |
| `E_DUPLICATE_HABIT` | 两条习惯重复 |

### 结构门——warning

| 代码 | 触发 |
| --- | --- |
| `W_EVIDENCE_SHORT` | 维度 `evidence` 归一化后少于 6 字符 |
| `W_NON_ACTIONABLE` | `next_step` 或 `training` 过短，或命中"多练 / 认真一点"等空话 |
| `W_SCORE_UNIFORM` | 六个维度评分完全相同 |
| `W_ALL_UNAVAILABLE` | 六个维度全部标「不适用」 |
| `W_UNAVAILABLE_WITHOUT_REASON` | 某维标「不适用」，但 `observation` 没写明原因 |

### 审计门——error（越界措辞）

| 代码 | 触发 |
| --- | --- |
| `A_CAUSE` | 诊断知识漏洞 / 给学生能力定级 |
| `A_LABEL` | 给学生贴标签（"粗心 / 马虎 / 思维混乱 / 不认真"） |
| `A_PLAN` | 排题量 / 复习计划 |
| `A_VARIANT` | 出变式题 / 出练习题 |
| `A_SOLUTION` | 给完整解答 / 整题重写 |
| `A_SCORE` | 评分 / 扣分 |

> 本技能不判对错；"算错 / 错在 / 写错"也属于越界，应当出现在 `math-error-diagnosis`，不在本技能的卡片里。

### 审计门——warning

| 代码 | 触发 |
| --- | --- |
| `W_POSITIVE_ABSENT` | 草稿里有划改痕迹，但没指出积极信号 |
| `W_RISK_UNHEDGED` | `risk` 说了后果却没有限定词 |
| `W_GRADE_MISMATCH` | 学段是小学/初中，却使用了元认知/策略导向措辞 |
| `W_MULTI_PROBLEM_DRAFT` | 草稿里出现两个以上题号标记，可能不止一道题 |

## 两道门都不验数学

`validate` 是结构门，`audit` 是措辞门，**两者都不验数学，也不验证版面观察是否属实**。
本技能只看版面，不判断计算对错；通过两道门只说明「卡片没越过结构线与措辞线」。
