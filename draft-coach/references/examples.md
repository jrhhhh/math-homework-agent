# 示例说明

`example/` 里是 7 份真实输出：4 张卡片（3 张正例 + 1 张反例）和 3 份 `refuse` 输出。本文把它们整理成可读说明，并给出**实跑的退出码**，不必再去翻 JSON。

**退出码是实跑得到的**，用本机解释器，工作目录 `d:/university learning/math-homework-agent`：

```bash
PY="D:/Program Files/anaconda3/python.exe"
"$PY" draft-coach/scripts/validate_output.py validate --card draft-coach/example/<名字>.json
"$PY" draft-coach/scripts/audit_output.py audit --card draft-coach/example/<名字>.json --draft "<配套草稿>" --strict
```

## 退出码总表

| 示例 | 类型 | `validate` | `audit` | `audit --strict` |
| --- | --- | --- | --- | --- |
| `high_school_cubic.json` | 正例卡 | 0 | 0 | 0 |
| `junior_high_substitution.json` | 正例卡 | 0 | 0 | 0 |
| `junior_high_transposition.json` | 正例卡 | 0 | 0 | 0 |
| `fabricated_error.json` | 反例卡 | 0 | 1 | 1 |
| `refuse_empty.json` | refuse 输出 | 不适用 | 不适用 | 不适用（由 `refuse` 产出，退出码 2） |
| `refuse_unreadable.json` | refuse 输出 | 不适用 | 不适用 | 不适用（退出码 2） |
| `refuse_out_of_scope.json` | refuse 输出 | 不适用 | 不适用 | 不适用（退出码 1） |

说明：`refuse_*.json` 不是卡片，`validate` / `audit` 不处理它们；它们是 `audit_output.py refuse --reason …` 的真实输出，退出码见表末。

## 正例 1：`high_school_cubic.json`（高中函数草稿）

配套草稿（逐字，来自 `draft-coach/tests/test_audit.py` 的 `CUBIC_DRAFT`）：

> 左上角写 x^3-3x 求极值；中间写 f'(x)=3x^2-3；下面写 3x^2=3 → x^2=1 → x=1（划掉）x=±1；右边写 f(1)=1-3=-2；右下角写 f(-1)=-1+3=2；底部写 极大值2 极小值-2

卡片要点：`error_check.errors` 为空（求导、解方程、代入三步都核对过，`scope` 里写明"未核验原题条件是否抄写正确"）。六维——组织度中（三步混在一片区域）、跳步低（3x²=3 直接到 x=±1，跳掉 x²=1）、涂改中（`correction_pattern.positive` 肯定"划掉后立刻补回 ±"）、试错低（只有求导一条路）、图形低（全篇无图）、利用率高。三条习惯：解方程跳步、动笔前不画图、草稿不分区。

退出码：`validate` 0 · `audit` 0 · `audit --strict` 0。

## 正例 2：`junior_high_substitution.json`（初中方程组草稿）

配套草稿（逐字，来自 `draft-coach/tests/test_audit.py` 的 `SUBSTITUTION_DRAFT`）：

> 解 2x+3y=12, x-y=1。写了代入法：由 x-y=1 得 x=y+1，代入得 2(y+1)+3y=12，然后划掉一大段，重新写 2y+2+3y=12 → 5y=10 → y=2 → x=3

卡片要点：`error_check.errors` 为空。六维——组织度中（划掉一大段后没标原因）、跳步高（每步落笔）、涂改中（`positive` 肯定"能在下一步之前停下来重写"）、试错低（只有代入法）、图形低、利用率高。三条习惯：涂改后不写原因、只用一个方法、不画图。

退出码：`validate` 0 · `audit` 0 · `audit --strict` 0。

## 正例 3：`junior_high_transposition.json`（初中移项草稿）

配套草稿：本仓库里这份草稿没有单独存档，逐字文本出自 [`docs/代表案例.md`](../../docs/代表案例.md) 的 D03 案例记录：

> 左边 2x+3=7；下面 2x=7+3=10；右边 x=5；中间划掉一次

（该草稿复原与卡片 `evidence` 完全对得上：`2x+3=7`、`2x=7+3=10`、`x=5`、`划改痕迹`。）

卡片要点：`error_check.errors` **有一条真错**——移项未变号，`2x=7+3=10` 应写成 `2x=7-3=4`，故 x=2 而非 5。`scope` 写明"只有草稿、没有原题，按草稿自身的目标式 2x+3=7 逐步核对到 x=5"。六维——组织度中、跳步中（除以 2 未落笔）、涂改中、试错低、图形低、利用率「不适用」（无最终解答）。三条习惯：移项时不变号、关键运算不落笔、涂改不留理由。

退出码：`validate` 0 · `audit` 0 · `audit --strict` 0。

## 反例：`fabricated_error.json`（结构门过、审计门不过）

配套草稿：与正例 1 相同的 `CUBIC_DRAFT`（见上）。

这份卡**故意做错三件事**，用来说明两道门的分工：

1. 报了一条草稿里根本没有的错误——`evidence` 写"草稿下面还写了一行 48÷4=12"，而草稿里 `48`、`4`、`12` 一个都没有。审计报 `W_ERROR_NOT_IN_DRAFT`，`candidates` 列出 `["48", "4", "12"]`。
2. 给学生贴标签——`observation` 写"你的思维比较混乱"。审计报 `A_LABEL`。
3. 写了题量计划——`training` 写"连续做 10 道解方程题"。审计报 `A_PLAN`。

另外它还漏了涂改维度的 `positive`（草稿里有 `（划掉）`），审计报 `W_POSITIVE_ABSENT`。

结果：**结构门退出 0**（它不查越界、也不查那条"错误"是否属实），**审计退出 1**，`--strict` 也退出 1。审计命中的代码：`errors = ["A_LABEL", "A_PLAN"]`，`warnings = ["W_ERROR_NOT_IN_DRAFT", "W_POSITIVE_ABSENT"]`。

> 这张卡正说明：两门必须都跑，且 `W_ERROR_NOT_IN_DRAFT` 必须人工过目。

## 三份 `refuse` 输出

`refuse` 只输出标准话术，**判断理由是模型给的**——脚本认不出请求是否越界。三份输出字段固定为 `action` / `error` / `message` / `reason` / `exit_code_meaning`。

| 文件 | `--reason` | `error` | 退出码 | 语义 |
| --- | --- | --- | --- | --- |
| `refuse_empty.json` | `empty` | 无草稿 | **2** | 没有检测到草稿内容 |
| `refuse_unreadable.json` | `unreadable` | 草稿无法识别 | **2** | 草稿太乱或图片不清晰，无法分析 |
| `refuse_out_of_scope.json` | `out_of_scope` | 超出范围 | **1** | 草稿没问题，但问题不归本技能管 |

读法：**2 = 草稿本身不能当证据**（没给 / 给了但用不了）；**1 = 草稿没问题，但这个问题不归本技能管**（比如要变式题或复习计划）。

生成命令与退出码（实跑）：

```bash
"$PY" draft-coach/scripts/audit_output.py refuse --reason empty        # 退出码 2
"$PY" draft-coach/scripts/audit_output.py refuse --reason unreadable   # 退出码 2
"$PY" draft-coach/scripts/audit_output.py refuse --reason out_of_scope # 退出码 1
```

## 两道门都不验数学

上表里三张正例卡的 `error_check` 是否真的说对了这个学生，脚本判不了。`validate` 只查结构，`audit` 只查证据在不在草稿里、有没有越过措辞边界。**没有人工复核的草稿检查卡不构成数学结论。**
