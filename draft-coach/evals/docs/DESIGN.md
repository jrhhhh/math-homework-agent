# Draft Coach Benchmark 设计规范

规则依据：`draft-coach/SKILL.md`。**评测器不修改技能的行为定义**，只按 SKILL.md 的既有要求度量行为。

## 0. 与既有材料的关系

| 既有材料 | 关系 |
| --- | --- |
| `tests/behavior-evaluation/draft-coach-2026-10-15/` | 12 条案例的小型对照评测（A/B 盲评 + 门层重放）。本基准是独立项目，**不替代它**；其中已设计好的对抗性案例可按 `provenance: "imported"` 迁入，但**答案与评分不迁**，避免用同一批结果重复声称。 |
| `draft-coach/scripts/validate_output.py` 与 `draft-coach/scripts/audit_output.py` | **两个外部脚本依赖**，存在且已核验。F 子集与各子集的自动项直接调用它们；常量在 `draft-coach/scripts/_rules.py`。 |
| `tests/behavior-evaluation/summarize.py` | 仅供旧评测使用，本基准不复用（指标集不同）。 |

**未配置任何模型 API。** 因此 `../evaluate.py` 不会自己调用模型：`baseline` / `skill` / `skill_gates` 三组的原始输出必须由宿主 agent 产出后保存成 `predictions/*.json`，或从别处 `replay`。脚本负责的是加载、重放门脚本、评分与报告。

## 1. 数据集划分

三个 split，是 `cases.jsonl` / `ground_truth.jsonl` 每行的一个字段：`development`、`validation`、`test`。

**防泄漏规则**：`template_id` 是划分的最小单位。同一 `template_id`（含只换数字的近重复）**必须整体落在同一个 split**。校验器 `../engine/schema_check.py` 会拒绝跨 split 的同模板案例。

`split: test` 的行是**留出集**：作者完成后不提交进仓库，仓库里只保留 [`../holdout_templates.json`](../holdout_templates.json)（预留的模板号）与说明。本批交付中 `split: test` 的行 **0 条**，见 [`../HOLDOUT.md`](../HOLDOUT.md)。

六个子集与目标规模：

| 子集 | 子集标识 | 第一阶段 | 正式版目标 | 本批实交 |
| --- | --- | ---: | ---: | ---: |
| A 数学错误定位 | `A_math_error_localization` | 100 | 100 | 见 README |
| B 证据忠实度 | `B_evidence_fidelity` | 60 | 60 | |
| C 六维习惯分析 | `C_dimension_analysis` | 60 | 60 | |
| D 输入边界与拒绝 | `D_boundary_refusal` | 50 | 50 | |
| E 复杂草稿场景 | `E_complex_drafts` | 60 | 60 | |
| F 输出与工具合规 | `F_output_tool_compliance` | 50 | 50 | |

上表右两列是**目标**，不是已完成量；实际条数由 schema 校验器在运行时统计并写进报告。

## 2. 评分分层

每一项指标都标注它属于哪一层，报告里**分开列，不混算**：

- **自动（automatic）**：确定性规则，重跑结果一致，不含模型判断。
- **模型辅助（model_assisted）**：由独立上下文的评审按固定评分卡给出结构化判定（如证据是否支持结论）。**不是** ground truth，报告里单列。
- **人工（human）**：`../engine/human_review.py` 导出的评分表，由人填写后回读。

**绝不把人工或模型辅助结果伪装成自动验证结果**，也不把格式正确当成数学正确。

## 3. 指标与计算公式

下表 `TP` / `FP` / `FN` 均指**错误条目**级别；匹配方式见 §3.1。

### A 数学错误定位

| 指标 | 层 | 公式 |
| --- | --- | --- |
| `error_precision` | 自动 | `TP / (TP + FP)`，`TP`、`FP` 只按 §3.2 的合法计数集统计 |
| `error_recall` | 自动 | `TP / N_required`，`N_required` = `must_report=true` 且 `kind ∈ {root, independent}` 的条目数 |
| `error_localization` | 自动 | `N_anchor_hit / N_required`，锚点逐字命中草稿且匹配到 gold 条目才算命中 |
| `location_descriptor_correct` | 模型辅助 | 位置描述与 gold `location` 指同一步的比例 |
| `fix_correctness` | 模型辅助＋人工 | 匹配上的错误里，`minimal_fix` 方向正确的比例 |
| `no_error_identification` | 自动 | `gold_errors` 为空的案例上，答案 `errors` 也为空的比例 |
| `propagation_quality` | 自动＋模型辅助 | 有 `propagated` 条目的案例上，答案引用了根错锚点且未把派生步骤当作独立错误的比例 |

### B 证据忠实度

| 指标 | 层 | 公式 |
| --- | --- | --- |
| `evidence_existence_rate` | 自动 | 预测的每条错误里，`evidence` 至少含一个草稿真实存在的记号的比例 |
| `evidence_support_rate` | 模型辅助＋人工 | 证据存在**且**能支持该结论的比例 |
| `explanation_correctness` | 模型辅助＋人工 | 错因解释在数学上成立的比例 |
| `fix_correctness` | 模型辅助＋人工 | 同上（与 A 共用定义，便于两子集对比） |
| `minimal_fix_compliance` | 自动＋模型辅助 | 未触发 `A_SOLUTION`（整题重写）**且**改动范围限于被指出的那一步的比例 |

### C 六维习惯分析

| 指标 | 层 | 公式 |
| --- | --- | --- |
| `dimension_completeness` | 自动 | 六维齐全、键名固定、每维四字段齐全（由 `validate` 裁决） |
| `dimension_label_match` | 自动 | 标签与 gold 一致的维度数 / 可判定维度数（`unevaluable` 维度不计入分母） |
| `dimension_evidence_grounded` | 模型辅助 | `observation`/`evidence` 出自草稿、未编造涂改/试错/图形的比例 |
| `positive_signal` | 自动 | `positive_expected=true` 的维度上，答案给出了积极信号的比例 |
| `risk_form` | 自动 | `risk` 为假设句的比例（复用 `W_RISK_UNHEDGED` 的规则） |
| `utilization_handling` | 自动 | 无最终解答时不给出具体利用率评分的比例（用 `不适用`） |

### D 输入边界与拒绝

| 指标 | 层 | 公式 |
| --- | --- | --- |
| `action_accuracy` | 自动 | 实际动作与 `expected_action` 一致的比例；`analyze`＝产出卡片，`clarify`＝未产卡且有追问，`refuse`＝未产卡且命中标准话术或明确拒绝 |
| `refuse_reason_accuracy` | 自动＋模型辅助 | 应 `refuse` 时理由（`empty`/`unreadable`/`out_of_scope`）正确的比例 |
| `over_refusal_rate` | 自动 | `expected_action=analyze` 却被拒绝的比例（越低越好） |
| `boundary_violation_rate` | 自动 | 命中 `audit` A 组越界（贴标签/诊断漏洞/计划/变式题/完整解答/评分）的比例 |
| `clarify_quality` | 模型辅助 | 追问是否问到点上（问的是「这道题要求什么」而不是无关内容） |

### E 复杂草稿场景

| 指标 | 层 | 公式 |
| --- | --- | --- |
| `multi_problem_handling` | 自动＋模型辅助 | 多题草稿上先分块、并声明归属是否确认的比例 |
| `evaluable_scope_respected` | 模型辅助＋人工 | 对 `unevaluable_scope` 中的事项**没有**下确定结论的比例 |
| `cross_block_false_positive` | 自动 | 把不同块的条件与结果对在一起造成的假错数（越低越好） |
| `mixed_content_reading` | 模型辅助 | 公式/文字/图形混排被正确读入的比例 |
| `complexity_math_accuracy` | 自动 | 复用 A 的 `error_precision` / `error_recall` |

### F 输出与工具合规

| 指标 | 层 | 公式 |
| --- | --- | --- |
| `json_parseable` | 自动 | 卡片能被 `json.loads` 解析的比例 |
| `structure_valid` | 自动 | 重放 `validate` 退出码为 0 的比例 |
| `audit_clean` | 自动 | 重放 `audit --strict` 退出码为 0 的比例 |
| `tool_log_fidelity` | 自动 | `tool_log` 记录的退出码与 runner 重放结果一致的比例；不一致即 `S5` |
| `exit_code_reported` | 自动 | 产卡案例中真的记录了 `validate` 退出码的比例 |
| `retry_policy_followed` | 人工 | 未过门时是否定点修改且 ≤3 轮（需要 transcript，本批未采集） |

### 3.1 匹配方式

预测的错误条目与 gold 条目匹配，采用**锚点重叠**：

1. 取预测条目 `evidence` 里所有「记号」（数字与 ASCII 标识符，复用 `draft-coach/scripts/_rules.py` 的 `draft_tokens` 口径）与位置描述；
2. 若某 gold 条目的某个 `evidence_anchor` 逐字出现在预测的 `evidence` 或 `location` 中，即判为该 gold 条目被匹配；
3. 一条预测最多匹配一条 gold；多条预测命中同一 gold 时，第一条为 `TP`，其余按 `FP` 计。

**这仍不等于数学正确。** 锚点匹配只能证明「引用的是草稿里那处」，不能证明「那处真的错了」。所以 `evidence_support_rate`、`explanation_correctness`、`fix_correctness` 一律走模型辅助或人工。

### 3.2 合法计数集（避免重复计数）

`error_precision` / `error_recall` 的分子分母都**只**包含 `kind ∈ {root, independent}` 且 `must_report = true` 的 gold 条目，以及匹配到它们的预测。

- 匹配到 `kind = propagated` 条目的预测：**不计 TP、不计 FP**（不是多报）。
- 匹配到 `must_report = false` 条目的预测：同上。
- 完全匹配不上任何 gold 条目的预测：计 `FP`。

### 3.3 归一化与总分

每个子集先归一到 0～100：

```
subset_score = 100 × Σ(metric_weight_i × metric_value_i) / Σ(metric_weight_i)
```

子集内各指标默认等权（可在 `../config.json` 覆盖）。总分：

| 维度 | 子集 | 初始权重 |
| --- | --- | ---: |
| 数学判错准确性 | A | 30% |
| 证据忠实度与最小修改 | B | 20% |
| 六维观察质量 | C | 15% |
| 边界与拒绝行为 | D | 15% |
| 复杂草稿处理 | E | 10% |
| 输出与工具合规 | F | 10% |

```
total = Σ(weight_s × subset_score_s)
```

**权重是初始设计，需通过试运行校准**；`../config.json` 里可改，报告必须打印实际使用的权重。

## 4. 硬门槛：严重失败

严重失败**单独统计，不被任何高分抵消**。分类与判定方式见 [标注指南 §8](ANNOTATION_GUIDE.md)；`../config.json` 的 `severe_failures` 是权威映射。

`S5`（伪造工具执行记录）是唯一必须由**真实重放**判定的：`../evaluate.py` 把 `card` 重新喂给 `draft-coach/scripts/validate_output.py` 与 `draft-coach/scripts/audit_output.py`，比对 `tool_log` 里记录的退出码。声称跑了而实际跑不出那个码，即记为伪造。

**有限样本中没有观察到严重失败，不代表真实使用中绝不会失败。**

## 5. 报告要求

`../evaluate.py` 产出的报告至少包含：

1. 各子集得分（0～100）与总分；
2. 每项指标的**分子/分母**（不允许只给比率）；
3. 严重失败条数与逐条案例；
4. 分层结果：按 `difficulty`、`category`、`draft_source`；
5. 二元比例给出 Wilson 置信区间（样本量小时明确标注区间很宽）；
6. 三个层次（自动/模型辅助/人工）分别列出，未完成的层标注 `未运行`；
7. 与 `baseline` 的对照，以及 `skill` → `skill_gates` 的增量。

## 6. 三个实验组

| 组 | 条件 | 门脚本 |
| --- | --- | --- |
| `baseline` | 不加载 Skill | 不跑 |
| `skill` | 加载 `SKILL.md`，按其流程作答 | 不跑 |
| `skill_gates` | 加载 `SKILL.md` | **真跑** `validate` 与 `audit --strict`，并记录退出码 |

要求：同一批样本、固定运行参数、保存原始输出与真实退出码。本仓库无模型 API，三组输出由宿主 agent 产出后存成 `predictions/<arm>.json`；`../evaluate.py` 只做加载、重放、评分。**未运行的组在报告里标 `未运行`，不编造结果。**

## 7. 本批已知缺口（必须在报告中保留）

1. `split: test` 留出集：0 条。原因：正式版目标 380 条，本批优先把 dev/val 做扎实；留出集应由未参与设计的人另行撰写，避免作者偏见。
2. `retry_policy_followed` 需要完整 transcript（多轮门禁失败后定点修改的过程），本批未采集。
3. `S3`（图像歧义下硬判）依赖 `image_confirmed: false` 的图片案例，本批只有文字还原案例，因此该项**未运行**。
4. 没有人类标注者参与，因此**不声称标注一致性**；双人标注流程只是流程设计。
5. 权重未经试运行校准。
