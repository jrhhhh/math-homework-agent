# 标注指南（Ground Truth Annotation Guide）

本文件是案例标注的唯一口径。**规则以 `draft-coach/SKILL.md` 为唯一主要依据**；评测器不改变技能的行为定义。

所有案例都是 `schemas/case.schema.json` 的实例。写完后必须通过：

```bash
python3 draft-coach/evals/engine/schema_check.py
```

校验器会强制核对**每条 `evidence_anchor` 是否逐字出现在 `input.draft` 里**——这是数据自身的「证据必须有草稿依据」，写错锚点的案例会被直接拒收。

---

## 1. 什么算错误

一处**计算或形式变形**在数学上不成立，即为错误。只标能落到草稿具体记号上的错误。

算错误：
- 算术算错（`7+3` 写成 `11`）。
- 移项不变号（`x+7=3 → x=3+7`）。
- 去括号漏乘（`2(x+3)` 展开成 `2x+3`）。
- 符号、指数、系数抄错或写错。
- 求导、因式分解、极限、矩阵运算等规则用错。
- 分类讨论漏情况（`x²=1 → x=1`，在**题设未限制**符号时）。

**不算错误**（这些进 `gold_correct_steps`，报它就是假错）：
- 合法跳步（见 §2）。
- 已经划掉、旁边补写了正确式子的旧笔迹（见 §3）。
- 题设已经排除的分支被正确舍去（`x>0` 下由 `x²=1` 只取 `x=1`）。
- 与本题无关但正确的中间变形（例如两边同乘一个非零常数）。
- 纯习惯问题（草稿不分区、跳步、不画图）——**这些是六维观察，不是 `errors`**。

> 跳步本身不是错误。同一处既可能进 `errors`（结果确实错了），也可能只进 `skipping`（结果对但没法复核）。两处都写时要分清；**把仅属跳步的步骤写进错误清单即为假错**。

## 2. 什么是合法跳步

省略的步骤满足全部三条，才算合法跳步：
1. 省略的是常规运算（移项、合并同类项、约分、代入求值），不是需要讨论或分类的步骤；
2. 结论可以逐步复核，且复核结果与草稿写的一致；
3. 省略没有掩盖任何需要判断的分支。

`3x²=3 → x=±1`（跳过 `x²=1`）：结论对，属合法跳步，**不进 errors**，进 `skipping` 观察。
`x²=1 → x=1`（题设未限制 x>0）：**漏根**，是错误，进 errors。
`x²=1 → x=1`（题设已给 x>0）：不是错误（见 §1）。

## 3. 什么是已纠正的旧错误

草稿上被划掉、并在旁边写下正确式子的那一处，**不是当前有效错误**：
- 进 `gold_correct_steps`（说明「此处已自我纠正」），并在 `correction_pattern.positive_expected = true`。
- 答案若把它当作现存错误报出来（「你把 3 写成了 -3，这处错了」而现存结论是对的），**属于假错**。

判断依据只看草稿的可见状态：划线＋旁边补写＝已纠正。若只有划线、没有补写、后续仍沿用旧值，则旧值**仍是错误**。

## 4. 错误传播与独立错误

`kind` 三选一，**这是避免重复计数的关键**：

- `root`：根错。后面的偏差由它引起。`propagates_to` 列出被带偏的 error_id。
- `propagated`：**在上游错误的前提下，这一步的运算本身是对的**。典型：`2x+3=14`（漏乘）之后写 `2x=11`，14−3=11 没错。
- `independent`：与前后无关的独立错误（同一步里同时出现漏乘和抄错数字）。

`propagates_to` 里的每个 id 必须是本案例 `gold_errors` 中 `kind = "propagated"` 的条目。

**计分规则（写死在 `../config.json`）**：`error_precision` / `error_recall` 只统计 `kind ∈ {root, independent}` 且 `must_report = true` 的条目。`propagated` 条目**不进分子也不进分母**——答案单独列出它不算多报，不列也不算漏报。传播识别质量由单独指标 `propagation_quality` 衡量：答案是否把最终结果偏差归因到根错那一步。

## 5. 证据存在，但不支持结论

这两种情况必须分开标：

| 情形 | 例子 | 怎么记 |
| --- | --- | --- |
| 证据**不存在** | 答案引用「草稿下面写的 48÷4=12」，草稿里没有 48、4、12 | 严重失败（编造证据），自动判定：`evidence_anchor` 命中不了 |
| 证据**存在但**不支持结论 | 引用 `2x=11`（真的在草稿上），却断言「这里除法算错了」——该处其实是移项 | 不是严重失败，但 `evidence_support = false`，进模型辅助/人工复核 |
| 证据存在、结论也成立、但**改法错** | 指出 `2x=11` 应改成 `2x=8`，却写成 `2x=12` | `fix_correctness = false` |
| 证据存在、结论成立、改法对，但**改动范围过大** | 指出漏乘，却把整题重写一遍（触发 `A_SOLUTION`） | `minimal_fix_compliance = false` |

**绝不能只用「字符串是否出现」判定证据正确**：§5 后三种情形都必须由模型辅助或人工判定，报告里与自动指标分开列。

## 6. 什么时候请求澄清、什么时候拒绝

| 预期动作 | 触发条件 | 例子 |
| --- | --- | --- |
| `analyze` | 有可读草稿，能看出在算什么 | 完整草稿、缺原题但内部自洽可查 |
| `clarify` | 有草稿，但**看不出在算什么**或**题目归属定不下来** | 只有三个孤立数字；一张纸上两块内容分不清各属哪题 |
| `refuse` | 没有草稿 / 草稿根本无法识别 / 请求不归本技能 | 只给题目；照片反光认不出；要变式题与复习计划 |

`refuse` 必须同时给出 `refuse_reason`：`empty`（没给草稿，退出码 2）、`unreadable`（给了但用不了，退出码 2）、`out_of_scope`（草稿没问题但不归本技能管，退出码 1）。

缺原题但草稿可读 → **是 `analyze`，不是 `clarify`**；此时 `unevaluable_scope` 必须写明「题意是否抄对」「解题方向是否正确」，`scope` 未声明降级即为不合格。

> **动作分类里没有 `transcribe`**：它是 `analyze` 之前的中间步（机器出候选、学生逐行核对），暂不进入动作分类。含 `machine_transcription` 的案例仍标 `analyze`，用 `input.image_confirmed` 记录确认状态；识别准确率与"学生是否真的核对过"都不在本评测能验证的范围内。

## 7. 六维评分如何判定

标签只有 `高 / 中 / 低`；**完整卡**里 `draft_to_solution` 在**未提供最终解答**时可用 `不适用`。每个维度都必须写 `basis`，且 `basis` 只能引用草稿里看得见的记号。

> 版面卡（`analysis_basis: "layout_only"`）里有更多维度标 `不适用`，但**当前评测集没有这类案例**（`schema_check.py` 仍按完整卡的规则校验金标）。为版面卡造案例需要同时放宽 `E_DRAFT_SOURCE_CONFLICT`、`E_DIM_LABEL` 与 `gate_replay` 的草稿假设，属独立跟进项。

| 维度 | 高 | 中 | 低 |
| --- | --- | --- | --- |
| `organization` | 有明确分区，可追溯 | 有顺序、无分区 | 东写一块西写一块，无法追溯 |
| `skipping` | 关键步骤全部落笔 | 偶尔跳简单步骤 | 跳步严重，关键步骤不落笔 |
| `correction_pattern` | 极少涂改，或涂改有标记与理由 | 有涂改，看得出修改意图 | 涂改频繁，或改后不留理由 |
| `trial_and_error` | 主动试多种方法并标注 | 偶尔尝试备选 | 一条路走到黑 |
| `graphic_use` | 主动画图、标注完整 | 偶尔画、不完整 | 完全不画图 |
| `draft_to_solution` | 草稿结果全部用上 | 部分利用 | 草稿与正解脱节 |

标注时的硬性约定：

- **`graphic_use` 在纯代数草稿上标 `unevaluable: true`**：草稿里没有图形，而题面也不要求画图。此时只检查答案有没有**编造**图形（evidence 必须出自草稿），标签本身不判对错。
- 草稿里有涂改痕迹且已自我纠正 → `correction_pattern.positive_expected = true`；答案没给出积极信号，`positive_signal` 记 false。
- 未提供最终解答 → `draft_to_solution.label = "不适用"`。答案若在无最终解答时给了具体评分，记 `utilization_handling = false`。
- `risk` 字段必须是假设句（「若…可能…」）。写成断言（「这会导致你错」）记 `risk_form = false`。
- 六个维度必须在答案里齐全、键名固定、每维四字段齐全，这部分由 `F` 子集的结构校验自动判。

## 8. 硬门槛：哪些行为是严重失败

严重失败**单独统计**，不被任何高分抵消。逐条列在 `forbidden_behaviors`，并由 `../config.json` 的 `severe_failures` 映射到自动或人工判定：

| 编号 | 严重失败 | 判定方式 |
| --- | --- | --- |
| `S1` | 凭空编造草稿证据（引用草稿里没有的记号） | 自动：预测证据锚点全部命中不了任何 gold 条目且草稿里也不存在 |
| `S2` | 把明确正确的步骤误判为错误 | 自动：假阳性的证据锚点落在 `gold_correct_steps` 上 |
| `S3` | 关键图像歧义下直接下确定结论 | 人工（`image_confirmed: false` 的案例） |
| `S4` | 没有草稿却伪造草稿分析 | 自动：`input.draft` 为 null 却产出了非空 `errors` |
| `S5` | 伪造工具执行记录 | 自动：`tool_log` 里的退出码与 runner 重放的真实退出码不一致 |
| `S6` | 明显违反技能禁止行为（贴标签 / 诊断漏洞 / 出变式题 / 排计划 / 给整题重写 / 评分） | 自动规则扫描（复用 `audit` 的 A 组）＋人工复核 |

**有限样本中没有观察到严重失败，不代表真实使用中绝不会失败。** 报告必须把严重失败数与得分并列。

## 9. 完整示例案例

以下是 `MATH-01`，作为格式与粒度的样板。注意锚点全部逐字出现在 `draft` 里。

```json
{
  "case_id": "MATH-01",
  "template_id": "tpl-alg-distribute-01",
  "subset": "A_math_error_localization",
  "split": "development",
  "category": "error_propagation",
  "difficulty": "medium",
  "grade_level": "初中",
  "input": {
    "prompt": "帮我看看草稿算得对不对。题目：解方程 2(x+3)=14。草稿：第一行写 2(x+3)=14；第二行写 2x+3=14；第三行写 2x=11；第四行写 x=5.5。",
    "problem": "解方程 2(x+3)=14。",
    "draft": "第一行写 2(x+3)=14；第二行写 2x+3=14；第三行写 2x=11；第四行写 x=5.5。",
    "final_solution": null,
    "draft_source": "text_reconstruction"
  },
  "expected_action": "analyze",
  "refuse_reason": null,
  "gold_errors": [
    {
      "error_id": "MATH-01-E1",
      "kind": "root",
      "propagates_to": ["MATH-01-E2", "MATH-01-E3"],
      "type": "algebra",
      "severity": "major",
      "location": "第二行",
      "evidence_anchor": ["2x+3=14"],
      "evidence_note": "去括号时只把 2 乘给了 x，漏乘了 3：2(x+3) 应展开为 2x+6，草稿写成 2x+3。",
      "cause": "分配律只用了一半，常数项没有乘。",
      "minimal_fix": "把第二行改成 2x+6=14。",
      "must_report": true
    },
    {
      "error_id": "MATH-01-E2",
      "kind": "propagated",
      "propagates_to": [],
      "type": "transposition",
      "severity": "minor",
      "location": "第三行",
      "evidence_anchor": ["2x=11"],
      "evidence_note": "在上一步 2x+3=14 的前提下，移项得 2x=14-3=11 本身没算错；错的是上一步的方程。",
      "cause": "承接第二行的错误方程，不是独立的运算失误。",
      "minimal_fix": "第二行改正后此处应为 2x=8。",
      "must_report": false
    },
    {
      "error_id": "MATH-01-E3",
      "kind": "propagated",
      "propagates_to": [],
      "type": "arithmetic",
      "severity": "minor",
      "location": "第四行",
      "evidence_anchor": ["x=5.5"],
      "evidence_note": "由 2x=11 得 x=5.5，除法本身正确；结果错是因为前面两行已经偏了。",
      "cause": "承接上游错误。",
      "minimal_fix": "第二行改正后最终结果应为 x=4。",
      "must_report": false
    }
  ],
  "gold_correct_steps": [],
  "gold_dimensions": {
    "organization": {"label": "中", "basis": "四行从上到下依次排列，有基本顺序，但没有分区。"},
    "skipping": {"label": "高", "basis": "去括号、移项、除法各占一行，关键步骤都落笔了。"},
    "correction_pattern": {"label": "高", "basis": "整张草稿没有涂改痕迹。"},
    "trial_and_error": {"label": "低", "basis": "只有一条推导路径，没有第二种做法。"},
    "graphic_use": {"label": "低", "basis": "纯代数方程，草稿里没有图形。", "unevaluable": true},
    "draft_to_solution": {"label": "不适用", "basis": "没有提供最终解答，无法判断草稿转化率。"}
  },
  "evaluable_scope": [
    "第二行去括号是否漏乘常数项",
    "第三、四行相对上一行是否自洽",
    "四步的行序与涂改痕迹"
  ],
  "unevaluable_scope": [
    "学生是否理解分配律（属知识诊断，不在本技能范围）"
  ],
  "expected_behaviors": [
    "报出去括号漏乘这一条，并写明锚点 2x+3=14",
    "说明第三、四行是承接上游错误，不把它们当成两个独立错误",
    "指出该处错误的最小修改是 2x+6=14，最终应为 x=4",
    "skipping 判为高：有错不等于跳步"
  ],
  "forbidden_behaviors": [
    "把第三行 2x=11 的移项本身说成运算错误",
    "诊断学生「不懂分配律」",
    "给整题重写或完整解答",
    "把 skipping 判为低（草稿并未跳步）"
  ],
  "severity": "medium",
  "provenance": "synthetic",
  "metrics": [
    "error_precision", "error_recall", "error_localization",
    "fix_correctness", "propagation_quality", "evidence_existence_rate"
  ],
  "notes": "E2、E3 是 propagated，不进 Precision/Recall 分子分母；只在 propagation_quality 里考察答案有没有把偏差归因到第二行。graphic_use 标 unevaluable：纯代数题不画图正常，只检查是否编造了图形。"
}
```

## 10. 双人标注与仲裁（流程设计，本人单人执行）

本批案例由**单一作者**产出，因此**不声称标注一致性**。正式版应采用：

1. 两名标注者独立标注同一案例；`input`、`gold_errors`、`gold_dimensions` 分别比对。
2. 一致 → 直接入库。不一致 → 进入仲裁：先各自只引用草稿原文申辩，仲裁者按本指南 §1–§4 的口径裁定，并把分歧写进 `notes`。
3. 记录 `gold_errors` 的条目级一致率（Jaccard）与 `gold_dimensions` 标签一致率；低于阈值（建议 0.8）的模板整体退回重标。
4. 仲裁结论要回写进本指南，作为新口径。

第二轮修正时，**先改指南、再改案例**，避免同一分歧被反复用两套标准处理。
