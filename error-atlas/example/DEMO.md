# 一个完整的例子：从六道错题到一套只治这些毛病的题

> 本文档里的**每一段 JSON 输出都是本机真实运行结果**，原始记录见
> [real_output.txt](real_output.txt)。示例数据在 `example/`，可用
> `python3 example/build_cards.py` 重新生成（指纹按真实内容重算，不要手写）。

---

## 场景

一个初高中混班的学生，一个月里做错了六道题。每道题在**同伴的 `math-error-diagnosis`**
那边已经过了一遍，留下了五份诊断结论（T1 与 T4 共用一次审查记录）。

学生把六道题连错因结论一起交给 `error-atlas`，问了一句：

> "我总在同一类地方出错，帮我看看我的错误有没有规律。"

然后他又补了一句：

> "看完了给我出几道题专门练。"

**第二句是关键。** 没有它，本技能在第一步之后就停下；
有了它，才进入第二段（`practice_authorized=true`）。

---

## 拿到手里的六道错题（`example/cases_junior.json`）

| 题号 | 题目 | 学生当时怎么错的 | 同伴结论 `cause.type` |
| --- | --- | --- | --- |
| T1 | 解方程：(x-1)/2 − (2x+3)/3 = 1 | 去分母时右边的常数 1 **漏乘** 6 | 运算错误 |
| T2 | 已知 f(x)=x²−4x+3，求与 x 轴交点个数 | 算出 Δ=4>0，却写"**只有一个交点**" | 分支/边界遗漏 |
| T3 | 解方程：2x+3=7 | 移项时 +3 **没变号**，写成 7+3 | 运算错误 |
| T4 | 解方程：2/(x−1) = 3 | **没先写定义域 x≠1** 就两边同乘 | 条件失效 |
| T5 | 解不等式：2x+3>7 | 解到 x>2 是对的，**往回写成 x<2**、边界也判错 | 条件失效 |
| T6 | 解方程：\|x−1\|=2 | 去绝对值**只取一支**，漏掉 x−1=−2 | 分支/边界遗漏 |

每题都带 `cause.method`（是怎么核验的）与 `cause.unresolved_items`（还有没有悬案）。
**这两项不是装饰**——它们决定了这道题能不能当证据用（见下面第三道坎）。

---

## 第一段：归因

```bash
python3 error_card_check.py validate --card example/junior_three_cases.json
python3 error_card_check.py audit    --card example/junior_three_cases.json \
                                     --cases example/cases_junior.json
```

### 结构门

```
{ "action": "validate",
  "method": "字段完整性 + 恰好 3 条模式 + 双词表白名单 + case_count 样本量 + 证据格式（含内容指纹）+ 画像聚焦与限定词",
  "errors": [], "warnings": [], "passed": true,
  "capability_note": "结构门不是数学判断：card 字段齐、样本量达标，不等于归因成立。" }
exit=0
```

### 证据门 + 引文门 + 越界门

```
{ "action": "audit",
  "method": "证据门（题号/内容指纹/原文支持/样本量/同伴结论状态）+ 引文门（自产错因/否定同伴/稳定判定/单题诊断）+ 越界门",
  "cases_seen":    ["T1", "T2", "T3", "T4", "T5", "T6"],
  "cases_touched": ["T2", "T3", "T4"],
  "errors": [], "warnings": [], "passed": true,
  "capability_note": "证据门是关键词匹配且忽略个位数字；case_count 与 cause.method 都是声明值，脚本查不出声明是否为真。" }
exit=0
```

`cases_touched` 是这次真正被引用的三道题（T2、T3、T4）——每条模式的 `evidence`
都从这三道题里取了原文，另外三道在这张卡里没被引用。

### 交到学生手上的病理图（节选真实字段）

```
跨题共同点
  第 [T1#558661c8ecd8] 题的去分母漏乘常数项、第 [T3#8445ad1935d7] 题的移项没变号，
  合起来是同一个「过程规范松动」：变形步骤被压缩、每一步没有逐项核对；
  第 [T4#1a15e1a7b99c] 题的定义域约束没写出来、第 [T5#6c68de6c7fc2] 题的不等号边界判错，
  则同属「条件加工缺位」这一类反复出现的条件漏检；
  而第 [T2#2f98b11345a9] 题与第 [T6#6179d7395640] 题都栽在「分支穷尽不足」上。

仍然成立的优势
  这六道题的最终计算都算对了：T1 的合并同类项、T2 的判别式求值、
  T4 解出的 x=5/3、T5 解出的 x>2 都没有算错，说明运算基本功是稳的。

能力画像（假设）
  这六道题共同指向的假设是：**步骤留痕与记录**偏弱——为了快而把变形压成一步，
  导致漏乘与不变号。样本量目前为六道题，属于初步判断，需再用新题验证。

下一个训练目标
  过程规范松动
```

三条模式各自长这样（第一条完整展开）：

| 模式 | 判断尺度 `cause_type` | 证据（点名题号 + 内容指纹） | 支撑题数 | 能力假设 | 立刻能做的动作 |
| --- | --- | --- | --- | --- | --- |
| 条件加工缺位 | 条件失效 | `[T4#1a15e1a7b99c]` 与 `[T5#6c68de6c7fc2]`：一个没写定义域、一个不等号边界判错 | 2 | 条件提取与转译 | 读题先圈出所有取值范围条件；遇到不等号先单独判定边界取不取 |
| 分支穷尽不足 | 分支/边界遗漏 | `[T2#2f98b11345a9]` 与 `[T6#6179d7395640]`：一个漏讨论三种情形、一个去绝对值只取一支 | 2 | 逻辑完备性 | 先在草稿上写下"要分几种情形"，再逐种填结论 |
| 过程规范松动 | 运算错误 | `[T3#8445ad1935d7]`，同批 `[T1#558661c8ecd8]` 也漏乘常数项 | 2 | 步骤留痕与记录 | 每步只写一个变形，移项和去分母各占一行，逐项标号核对 |

**请留意这张卡的三个"不"**：
它**没有**说"你粗心"（那是对人不对事）、
**没有**说"你逻辑能力一直很弱"（那是稳定判定，同伴明令禁止，本技能用 `A_STABLE_JUDGMENT` 驳回）、
也**没有**重新诊断哪一道题错在哪（那是同伴的活，本技能只能**引用** `cause_type`）。
画像那句写的是"**假设**……属于初步判断，需再用新题验证"。

---

## 第二段：出题（因为学生明确要求了）

```bash
python3 error_card_check.py practice --card example/practice_with_answers.json --verify-answers
```

### 门的结果

```
{ "action": "practice",
  "method": "授权门 + 绑定门（pattern_ref / 样本量 / 覆盖 / 难度三档 / 去重）+ 答案核验门（精确有理数代回）",
  "referable_patterns": { "1": "条件加工缺位", "2": "分支穷尽不足", "3": "过程规范松动" },
  "errors": [],
  "warnings": [
    { "code": "W_NO_SOLUTION_BASIS", "id": "P4", "status": "skipped",
      "reason": "题干不是可解析的一元/二元一次方程（组）",
      "detail": "超出可判定范围，明确跳过——不假装验过" },
    { "code": "W_NO_SOLUTION_BASIS", "id": "P5", "status": "skipped",
      "reason": "题干不是可解析的一元/二元一次方程（组）", … } ],
  "passed": true,
  "answer_verification": {
    "checked": [
      { "id": "P1", "status": "verified", "solved": { "x": "2" },
        "note": "精确有理数代回成立（工具辅助核验，非独立验证）" },
      { "id": "P2", "status": "verified", "solved": { "x": "2" }, … },
      { "id": "P3", "status": "verified", "solved": { "x": "2" }, … } ],
    "problems": [],
    "skipped": [ { "id": "P4", "reason": "题干不是可解析的一元/二元一次方程（组）" },
                 { "id": "P5", … } ] } }
exit=0
```

**读法**：P1–P3 是真算过的——脚本把答案代回原方程，用 `fractions.Fraction`
精确有理数运算验证成立。P4–P5 是二次函数／抛物线题，超出可判定范围，
脚本**明确 skipped 并写出原因**，不假装验过。

---

## 学生拿到的那张纸（只有题干，没有答案）

> **练习：针对你反复出现的三个毛病，各配了题**
>
> **一、同型巩固**
> 1. 解方程：2x+3=7。
> 2. 解方程：5−2x=1。
>
> **二、变式迁移**
> 3. 若 x>0 且 2x+3=7，求 x 的值。
> 4. 已知二次函数 f(x)=x²−4x+3，求它与 x 轴交点的个数。
>
> **三、综合拔高**
> 5. 已知直线 y=x+1 与抛物线 y=x²−6x+5，求它们的交点个数。
>
> 做完再对答案。每题括号里是它治哪个毛病，自己对一下是不是踩过。

| 题号 | 治的模式 | 难度档 |
| --- | --- | --- |
| P1、P2 | 过程规范松动 | 同型巩固 |
| P3 | 条件加工缺位 | 变式迁移 |
| P4 | 分支穷尽不足 | 变式迁移 |
| P5 | 分支穷尽不足 | 综合拔高 |

## 另存给家长／教师的那一页（卡片里的 `answer` + `solution_steps`）

| # | 题干要点 | 答案 | 关键步骤 | 治的模式 |
| --- | --- | --- | --- | --- |
| P1 | 2x+3=7 | x=2 | 移项 2x=7−3=4；同除以 2 得 x=2。**移项时 +3 变成 −3（变号）** | 过程规范松动 |
| P2 | 5−2x=1 | x=2 | 移项 −2x=1−5=−4；同除以 −2 得 x=2。两次符号变化都要逐项核对 | 过程规范松动 |
| P3 | x>0 且 2x+3=7 | x=2 | **先记下约束 x>0**；解得 x=2，满足 x>0，故 x=2 | 条件加工缺位 |
| P4 | f(x)=x²−4x+3 与 x 轴交点个数 | 2 个 | Δ=16−12=4>0，两个不同实根。**注意与 Δ=0、Δ<0 对照** | 分支穷尽不足 |
| P5 | y=x+1 与 y=x²−6x+5 交点个数 | 2 个 | 令 x+1=x²−6x+5 得 x²−7x+4=0；Δ=49−16=33>0，两个交点 | 分支穷尽不足 |

**答案与学生题干是分开存放的两个字段**（`student_prompt` vs `answer`/`solution_steps`）。
这不是格式洁癖：上游明确要求"是否展示答案遵从用户要求"，
而 `E_ANSWER_IN_PROMPT` 这道判据会**驳回**把答案写进题干的卡片。

---

## 这个例子到底"个性化"在哪

拿它和一个通用出题器比一比：

| | 通用出题器："给我来 5 道一元二次方程" | 本例 |
| --- | --- | --- |
| 出题依据 | 知识点 + 难度 | **这个学生的三条错误模式** |
| 每题绑定的东西 | 无 | **`pattern_ref` 指回病理图的第几条模式** |
| 样本门槛 | 无 | 该模式必须有 **≥2 道题**支撑才准出题 |
| 覆盖要求 | 无 | 三个模式**一道都不能漏**（`E_PATTERN_UNCOVERED`） |
| 难度要求 | 随便 | **三档难度必须都出现** |
| 答案 | 常常直接给 | 与题干**分离**，且 P1–P3 是**真算过**的 |

最容易看出差别的是 P3：**"若 x>0 且 2x+3=7，求 x"**。
它不是随便找的一道题——它精确地复现了 T4/T5 那个毛病：
题目里埋了一个约束条件，看学生会不会先把它摆出来。
换一个学生、换成"前提检验缺位"的模式，这一格就会换成完全不同的题。

**绑定关系就是"个性化"的技术定义。** 没有 `pattern_ref`，这套东西就退化成普通题库。

---

## 想自己复现全部输出

```bash
cd error-atlas
python3 example/build_cards.py                                          # 重算指纹、重建示例卡
python3 error_card_check.py patterns --problem "已知二次函数 f(x)=x^2-4x+3，求它与 x 轴交点的个数。"
python3 error_card_check.py validate --card example/junior_three_cases.json
python3 error_card_check.py audit    --card example/junior_three_cases.json --cases example/cases_junior.json
python3 error_card_check.py practice --card example/practice_with_answers.json --verify-answers
python3 verify_all_gates.py                                             # 59 条判据覆盖核验
```

想看**反面教材**，跑这三份教具（各自演示一道互相独立的门）：

```bash
python3 error_card_check.py validate --card example/bad_card.json            # 放行
python3 error_card_check.py audit    --card example/bad_card.json --cases example/cases_junior.json   # 驳回 8 条越界
python3 error_card_check.py validate --card example/bad_thin_card.json       # 驳回（样本量不足）
python3 error_card_check.py audit    --card example/bad_thin_card.json --cases example/cases_junior_thin.json  # 驳回 4 条证据问题
python3 error_card_check.py practice --card example/bad_practice_card.json --verify-answers            # 驳回 3 条出题问题
```

**Windows 注意**：`PATH` 里的 `python` / `python3` 可能是应用商店占位程序，
会静默失败。本机可用 `"D:/Program Files/anaconda3/python.exe"`。
