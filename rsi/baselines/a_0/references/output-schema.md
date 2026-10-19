# Math Solver 输出 Schema

机器可读输出必须是**一个 JSON 对象**，不要加 Markdown 代码围栏。字段名固定为英文；字段值默认用中文。调用方未要求机器可读输出时，用中文讲解，不必套此结构。

## 顶层字段

恰好六个，全部必需：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `status` | string | 整体状态，见下表 |
| `problem` | object | 题目解析结果 |
| `plan` | object | 求解计划 |
| `solution` | object | 推导与答案 |
| `verification` | object | 独立核验结果 |
| `teaching_notes` | object | 给下游教学技能的备注 |

除调用方明确扩展外，不添加其他顶层字段。默认结构门按本 schema **精确**校验；调用方若扩展 schema，需要同步调整门或提供扩展白名单，不能直接沿用默认门。

## `status`

| 值 | 含义 |
| --- | --- |
| `solved` | 完整达成题目目标，且核验通过 |
| `partially_solved` | 只完成部分目标，或只能给条件化解 |
| `needs_clarification` | 缺失或歧义信息阻止可靠作答 |
| `failed` | 存在未解决的数学错误，或目标无法成立 |

## `problem`

| 字段 | 类型 | 可空 | 说明 |
| --- | --- | --- | --- |
| `statement` | string | 否 | 原题陈述，保留原意 |
| `topic` | string | 否 | 主要数学主题 |
| `subtopics` | string[] | 否 | 相关概念或技巧 |
| `givens` | string[] | 否 | 明确给出的条件 |
| `variables` | string[] | 否 | 变量及其含义 |
| `constraints` | string[] | 否 | 定义域、区间、参数条件、几何约束等 |
| `goal` | string | 否 | 要求确定或证明的目标 |
| `requested_method` | string \| null | 是 | 用户明确指定的方法；没有则 `null` |
| `ambiguities` | string[] | 否 | 未解决的解释或缺失信息；没有则 `[]` |
| `assumptions` | string[] | 否 | 为继续求解而引入的假设；没有则 `[]` |

题目有歧义时写进 `ambiguities`，不要只藏在正文里。常见教材约定不能自动升级为题设条件。

## `plan`

| 字段 | 类型 | 可空 | 说明 |
| --- | --- | --- | --- |
| `main_idea` | string | 否 | 主要数学思想 |
| `method` | string | 否 | 实际采用的方法 |
| `prerequisites` | string[] | 否 | 需要的前提知识；没有则 `[]` |
| `steps` | string[] | 否 | 计划的步骤顺序 |

用户指定的方法不适用时，`method` 写替代方法，并在 `verification.issues` 或正文中说明原方法为何不适用。

## `solution`

| 字段 | 类型 | 可空 | 说明 |
| --- | --- | --- | --- |
| `derivation` | object[] | `failed` / `needs_clarification` 时可为 `[]` | 推导步骤 |
| `answer` | string \| null | 是 | 最终答案；没有可靠答案时 `null` |
| `conditions` | string[] | 否 | 答案成立的条件 |

`derivation` 每项恰好三个字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `step` | integer | 从 1 开始的正整数，建议连续递增 |
| `expression` | string | 数学表达式、等式、不等式或命题 |
| `justification` | string | 这一步所用的运算、定理或依据 |

`justification` 不能只写“显然”“整理得”。重要变形要说明依据；简单算术可以简述，但不能整步省略到无法复核。

`solved` 时 `derivation` 与 `answer` 都不能为空。

## `verification`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `status` | string | `passed` / `failed` / `needs_review` / `not_fully_verified` |
| `checks` | object[] | 实际执行的检查 |
| `issues` | string[] | 未解决的问题；没有则 `[]` |

`checks` 每项恰好三个字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `name` | string | 检查名称，例如“代回原方程”“检查增根” |
| `status` | string | `passed` / `failed` / `not_applicable` / `not_completed` |
| `details` | string | 检查了什么、结果如何 |

注意：

- 没有任何 `failed` 检查时，才可把 `verification.status` 写成 `passed`。
- `passed` 时 `issues` 必须为空。
- 有 `not_completed` 检查时，整体不能写 `passed`。
- 不把“同一段代数再算一遍”当作独立核验；优先换路线（代回、边界、逆运算、独立推导等）。
- 检查的 `details` 要写实际内容，不写“已验证”三个字。

## `teaching_notes`

| 字段 | 类型 | 可空 | 说明 |
| --- | --- | --- | --- |
| `key_insight` | string | 否 | 关键突破口 |
| `difficult_steps` | string[] | 否 | 高中生可能卡住的步骤 |
| `common_mistakes` | string[] | 否 | 与本题相关的常见错误 |
| `prerequisite_explanations` | string[] | 否 | 需要补充讲解的前置知识 |
| `alternative_method` | string \| null | 是 | 值得比较的第二方法；没有则 `null` |
| `follow_up_exercise_suggestion` | string \| null | 是 | 给下游的后续练习备注；不是本技能主动布置作业 |

这些是**教学备注**，不是数学推导的替代品。不要把 `exposed_gap` 式的长期能力标签、错因诊断或学生评价写进这里。

## 状态一致性

| 顶层 `status` | 对 `verification` 的要求 |
| --- | --- |
| `solved` | `verification.status = passed`；`issues = []`；`derivation` 与 `answer` 非空 |
| `partially_solved` | 不得声称整体 `passed`；用 `not_fully_verified` / `needs_review` / `failed` |
| `needs_clarification` | `verification.status = needs_review`；`ambiguities` 或 `issues` 非空 |
| `failed` | `verification.status = failed`；`issues` 写清未解决的错误或反例 |

`partially_solved` 配 `passed` 时，结构门只给告警：它可能表示“已完成的那部分确实核验通过”，也可能掩盖了未完成的目标。宿主必须人工确认 `conditions` 或 `issues` 已写清剩余部分。

## 禁止项

- 不添加 `confidence`、`probability_correct`、`accuracy`、`置信度` 等字段或说法。
- 不把 `assumptions` 中的内容伪装成题设。
- 不在 `solved` 下留未解决的 `issues`。
- 不在 `verification.checks` 里写没有实际执行过的工具核验。
- 不把 `derivation` 写成内部思维流水账；写可复核的数学步骤与依据。
