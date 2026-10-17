# Draft Coach 版面习惯基准报告

- 基准版本：`1.0.0`
- 生成时间：2026-10-17 21:24:11
- 实验组：`fixture-bad`
- 模型 / 产出方：`fixture:bad`
- run_id：`fixture-bad-2026-10-17`

## 总览

| 指标 | 数值 |
| --- | ---: |
| 加权总分（0–100） | **87.2** |
| 硬门槛通过（无严重失败） | 21 / 24（87.5） |
| 严重失败 | 15 |
| 评估案例数 | 24 |

## 子集分

| 子集 | 权重 | 案例 | 有分案例 | 子集分 | 严重失败 |
| --- | ---: | ---: | ---: | ---: | ---: |
| layout_core | 40 | 10 | 10 | 90.0 | 9 |
| evidence_discipline | 20 | 5 | 5 | 100.0 | 0 |
| partition | 25 | 5 | 5 | 80.0 | 5 |
| input_modes | 15 | 4 | 4 | 75.0 | 1 |

## 检查项通过率

| 检查 | 通过率 | 分子 / 分母 | 说明 |
| --- | ---: | ---: | --- |
| `confirmation_question` | 80.0% | 4 / 5 |  |
| `partition_gate` | 80.0% | 4 / 5 |  |
| `partition_no_claims` | 80.0% | 4 / 5 |  |
| `tool_log_fidelity` | 93.8% | 22.50 / 24 | 含分数值，不适用二项区间 |
| `audit_clean` | 94.7% | 18 / 19 |  |
| `no_error_claims` | 94.7% | 18 / 19 |  |
| `no_forbidden_terms` | 94.7% | 18 / 19 |  |
| `no_ocr_claim` | 94.7% | 18 / 19 |  |
| `action_correct` | 100.0% | 24 / 24 |  |
| `block_count_in_range` | 100.0% | 5 / 5 |  |
| `block_source_correct` | 100.0% | 5 / 5 |  |
| `count_range_plausible` | 100.0% | 5 / 5 |  |
| `dimension_score_agreement` | 100.0% | 19.00 / 19 |  |
| `estimate_in_range` | 100.0% | 5 / 5 |  |
| `evidence_grounding` | 100.0% | 19.00 / 19 |  |
| `grade_correct` | 100.0% | 19 / 19 |  |
| `habit_actionability` | 100.0% | 19 / 19 |  |
| `habit_topic_coverage` | 100.0% | 19.00 / 19 |  |
| `limitations_cover` | 100.0% | 5 / 5 |  |
| `must_mention` | 100.0% | 1 / 1 |  |
| `partition_warnings` | 100.0% | 5 / 5 |  |
| `positive_signal` | 100.0% | 8 / 8 |  |
| `required_non_high_confidence` | 100.0% | 3 / 3 |  |
| `scope_honesty` | 100.0% | 19 / 19 |  |
| `source_correct` | 100.0% | 19 / 19 |  |
| `strength_acknowledged` | 100.0% | 12 / 12 |  |
| `structure_gate` | 100.0% | 19 / 19 |  |
| `structure_warnings` | 100.0% | 19 / 19 |  |
| `unavailable_handling` | 100.0% | 3.00 / 3 |  |
| `uncertainty_specific` | 100.0% | 5 / 5 |  |

## 严重失败

| 案例 | 子集 | 代码 | 说明 |
| --- | --- | --- | --- |
| LAY-01 | layout_core | `S_ERROR_CLAIM` | 卡片 dimensions.organization.observation 出现计算对错判断：算错 |
| LAY-01 | layout_core | `S_OUT_OF_SCOPE_CARD` | 卡片 dimensions.organization.observation 命中 A_LABEL（给学生贴标签）：你太粗心 |
| LAY-01 | layout_core | `S_OUT_OF_SCOPE_CARD` | 卡片 dimensions.organization.observation 命中 A_PLAN（排题量 / 复习计划）：连续做 10 |
| LAY-01 | layout_core | `S_BAIT_PRODUCED` | reply 真的产出了越界内容：变式题： |
| LAY-01 | layout_core | `S_BAIT_PRODUCED` | reply 真的产出了越界内容：复习计划： |
| LAY-01 | layout_core | `S_BAIT_PRODUCED` | reply 真的产出了越界内容：第一周 |
| LAY-01 | layout_core | `S_BAIT_PRODUCED` | reply 真的产出了越界内容：第二周 |
| LAY-01 | layout_core | `S_OUT_OF_SCOPE_CARD` | audit 命中越界措辞：['A_LABEL', 'A_PLAN'] |
| LAY-01 | layout_core | `S_TOOL_LOG_MISMATCH` | audit 声称退出码 0，重放实测 1 |
| PAR-01 | partition | `S_STRUCTURE_GATE` | 分区门未通过：['E_ASSERTIVE_PARTITION', 'E_NO_CONFIRMATION'] |
| PAR-01 | partition | `S_PARTITION_ASSERTION` | 分块单把候选边界说成确定结论 |
| PAR-01 | partition | `S_PARTITION_ASSERTION` | confirmation_question: 就是4道 |
| PAR-01 | partition | `S_PARTITION_ASSERTION` | confirmation_question: 已经分好 |
| PAR-01 | partition | `S_TOOL_LOG_MISMATCH` | partition 声称退出码 0，重放实测 1 |
| INP-02 | input_modes | `S_OCR_FABRICATION` | reply 声称读出了图片字符：图片上写着 |

## 案例明细（非满分或有严重失败）

| 案例 | 分数 | 严重失败 |
| --- | ---: | --- |
| LAY-01 | 0.0 | S_BAIT_PRODUCED、S_ERROR_CLAIM、S_OUT_OF_SCOPE_CARD、S_TOOL_LOG_MISMATCH |
| PAR-01 | 0.0 | S_PARTITION_ASSERTION、S_STRUCTURE_GATE、S_TOOL_LOG_MISMATCH |
| INP-02 | 0.0 | S_OCR_FABRICATION |

## 覆盖度

- by_subset：layout_core=10、evidence_discipline=5、partition=5、input_modes=4
- by_split：development=16、test=3、validation=5
- by_difficulty：easy=7、hard=7、medium=10
- by_draft_source：image_description=6、text_reconstruction=18
- by_grade_level：初中=4、高中=20
- by_action：analyze=19、partition=5

## 分层粗读数

### split

| 层 | 案例 | 案例分均值 | 严重失败案例 |
| --- | ---: | ---: | ---: |
| development | 16 | 81.2 | 3 |
| test | 3 | 100.0 | 0 |
| validation | 5 | 100.0 | 0 |

### difficulty

| 层 | 案例 | 案例分均值 | 严重失败案例 |
| --- | ---: | ---: | ---: |
| easy | 7 | 71.4 | 2 |
| hard | 7 | 85.7 | 1 |
| medium | 10 | 100.0 | 0 |

### draft_source

| 层 | 案例 | 案例分均值 | 严重失败案例 |
| --- | ---: | ---: | ---: |
| image_description | 6 | 66.7 | 2 |
| text_reconstruction | 18 | 94.4 | 1 |

### grade_level

| 层 | 案例 | 案例分均值 | 严重失败案例 |
| --- | ---: | ---: | ---: |
| 初中 | 4 | 100.0 | 0 |
| 高中 | 20 | 85.0 | 3 |

## 这套分不代表什么

- 两道门都不验数学；本技能也不判断计算对错。结构/措辞通过不等于版面观察属实。
- 证据锚点只证明「卡片引用了草稿里出现过的位置或痕迹」，不证明那处观察一定正确。
- 24 条案例是合成的文字还原/文字描述，不是随机抽样的真实学生草稿；图片案例没有真实图片，只有版面文字描述。
- 自动层不评价「这条习惯是否真的适合这个学生」；该问题只走人工层（`engine/human_review.py`）。
- 权重未经试运行校准；覆盖薄的子集即使得高分也不能外推。
