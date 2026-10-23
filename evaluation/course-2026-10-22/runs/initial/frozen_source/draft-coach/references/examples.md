# 示例说明

`example/` 里是固定 fixture：5 张习惯卡、1 张整页分块单和 3 份 `refuse` 输出。本文给出**实跑的退出码**与逐份说明。

```bash
PY="D:/Program Files/anaconda3/python.exe"
"$PY" scripts/validate_output.py validate --card example/<名字>.json
"$PY" scripts/audit_output.py audit --card example/<名字>.json --draft "<配套草稿>" --strict
"$PY" scripts/partition_check.py validate --payload example/partition_sheet.json --strict
```

## 退出码总表

| 示例 | 类型 | `validate` | `audit` | `audit --strict` |
| --- | --- | --- | --- | --- |
| `high_school_cubic.json` | 习惯卡 | 0 | 0 | 0 |
| `junior_high_substitution.json` | 习惯卡 | 0 | 0 | 0 |
| `junior_high_transposition.json` | 习惯卡 | 0 | 0 | 0 |
| `layout_habits.json` | 短草稿习惯卡 | 0 | 0 | 0 |
| `out_of_scope_label.json` | 反例卡 | 0 | 1 | 1 |
| `partition_sheet.json` | 整页分块单 | 不适用 | 不适用 | 不适用（走分区门，退出 0） |
| `refuse_empty.json` | refuse 输出 | 不适用 | 不适用 | 不适用（退出码 2） |
| `refuse_unreadable.json` | refuse 输出 | 不适用 | 不适用 | 不适用（退出码 2） |
| `refuse_out_of_scope.json` | refuse 输出 | 不适用 | 不适用 | 不适用（退出码 1） |

## 正例 1：`high_school_cubic.json`

配套草稿：`左上角写 x^3-3x 求极值；中间写 f'(x)=3x^2-3；下面写 3x^2=3 → x^2=1 → x=1（划掉）x=±1；右边写 f(1)=-2；右下角写 f(-1)=2；底部写 极大值2 极小值-2`

要点：`scope` 写明只看版面、未读字符。分区中（几块靠位置区分、没有标号）；步骤分行低（解方程三步挤在一行）；划改中，`positive` 肯定"划掉后补写"；多路径低（只有一条线）；图形低（没有图）；留白与检验区中（底部写了结果，但没有检验区）。3 条习惯。

## 正例 2：`junior_high_substitution.json`

配套草稿：`解 2x+3y=12, x-y=1。写了代入法：由 x-y=1 得 x=y+1，代入得 2(y+1)+3y=12，然后划掉一大段，重新写 2y+2+3y=12 → 5y=10 → y=2 → x=3`

要点：划改段和重写段挤在同一块区域；`positive` 肯定"发现走不通后及时停下重写"；末尾三步挤在一行；没有标号区分路径。

## 正例 3：`junior_high_transposition.json`

配套草稿：`左边 2x+3=7；下面 2x=7+3=10；右边 x=5；中间划掉一次`

要点：三行位置清楚，但划改压在原行内部；行距偏紧；结果旁边没有检验区。

## 正例 4：`layout_habits.json`

配套草稿：`2x+3=7；2x=7-3=4；x=2`

要点：短草稿。`organization` 与 `graphic_use` 标「不适用」并写明原因；习惯只有 2 条。展示"不适用"和 1–3 条习惯的合法写法。

## 反例：`out_of_scope_label.json`

结构门退出 0，审计退出 1：`observation` 写了"你的思维比较混乱"（`A_LABEL`），`training` 写了"连续做 10 道解方程题"（`A_PLAN`）。这说明**结构门不查越界，两道门都要跑**。

## 整页分块单：`partition_sheet.json`

左上、右上、右下三块；右下与右上只隔一行，标成低置信、`separate_problem: false`，估计 2 道题、范围 2–3；`confirmation_question` 请学生确认 B3 是不是接着 B2；`limitations` 写明"只看版面，不读字符""块数不等于题目数""归属需要学生确认"。

## 拒绝出口

`refuse --reason empty|unreadable|out_of_scope` 的真实输出存在 `example/refuse_*.json`，退出码分别是 2、2、1。
