# Draft Coach Benchmark 评分报告

> 本报告由 `evals/evaluate.py` 生成，只重放已保存输出，不调用模型。

| 项目 | 值 |
| --- | --- |
| 实验组 | `skill` |
| run_id | `fixture-empty-skill` |
| 产出方 | fixture:make_fixture_predictions.py --mode empty（不是模型运行结果） |
| 模型说明 | 无模型参与。本文件只用于验证评测流程本身，不得当作任何模型的成绩。 |
| 评测案例数 | 38 |
| 缺输出案例 | 无 |
| 严重失败 | 0 条 |

> **警告：这不是模型运行结果。** 该预测文件的产出方标记为 'fixture:make_fixture_predictions.py --mode empty（不是模型运行结果）'，只能用来验证评测流程本身。

## 子集得分

| 子集 | 案例 | 配置权重 | 得分 | 自动层 | 模型辅助层 | 人工层 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `A_math_error_localization` | 8 | 30% | 25.0 | 2/19 | 未运行 | 未运行 |
| `B_evidence_fidelity` | 6 | 20% | 100.0 | 6/6 | 未运行 | 未运行 |
| `C_dimension_analysis` | 6 | 15% | 71.0 | 16.3/25 | 未运行 | 未运行 |
| `D_boundary_refusal` | 6 | 15% | 100.0 | 20/20 | 未运行 | 未运行 |
| `E_complex_drafts` | 6 | 10% | 100.0 | 6/6 | 未运行 | 未运行 |
| `F_output_tool_compliance` | 38 | 10% | 99.0 | 98/99 | 未运行 | 未运行 |

**总分：73.0 / 100**

## 覆盖度（自动层；分子/分母薄的地方必须看得见）

| 子集 | 案例范围 | 自动指标已用/可用 | 最小自动分母 | 实际参与计分的层 | 覆盖 |
| --- | --- | ---: | ---: | --- | --- |
| `A_math_error_localization` | 本子集案例 | 4/5 | 2 | automatic | **偏薄** |
| `B_evidence_fidelity` | 本子集案例 | 1/2 | 6 | automatic | **偏薄** |
| `C_dimension_analysis` | 本子集案例 | 5/5 | 1 | automatic | 完整 |
| `D_boundary_refusal` | 本子集案例 | 5/5 | 2 | automatic | 完整 |
| `E_complex_drafts` | 本子集案例 | 1/1 | 6 | automatic | 完整 |
| `F_output_tool_compliance` | 全部案例（跨子集指标） | 3/5 | 33 | automatic | **偏薄** |

> 自动层覆盖偏薄时分数仍可能是 100 分，必须连着分子分母一起读。最典型的情形：「什么错都不报」的空答案在「证据忠实度」上没有证据可判不忠实，于是拿到满分——它真正的失分在「数学错误定位」的 Recall 上。
>
> 模型辅助层与人工层未加载时记为「未运行」，**不是 0 分**，也不参与子集分；这也是「实际参与计分的层」一列存在的原因。

## 指标明细（分子/分母，不允许只给比率）

### `A_math_error_localization`

| 指标 | 层 | 分子/分母 | 比率 | 95% Wilson |
| --- | --- | ---: | ---: | --- |
| `error_precision` | automatic | — | 未运行 | — |
| `error_recall` | automatic | 0/6 | 0.000 | [0.000, 0.390] |
| `error_localization` | automatic | 0/6 | 0.000 | [0.000, 0.390] |
| `no_error_identification` | automatic | 2/2 | 1.000 | [0.342, 1.000] |
| `propagation_quality` | automatic | 0/5 | 0.000 | [0.000, 0.434] |
| `location_descriptor_correct` | model_assisted | — | 未运行 | — |
| `fix_correctness` | model_assisted | — | 未运行 | — |
| `explanation_correctness` | model_assisted | — | 未运行 | — |

### `B_evidence_fidelity`

| 指标 | 层 | 分子/分母 | 比率 | 95% Wilson |
| --- | --- | ---: | ---: | --- |
| `evidence_existence_rate` | automatic | — | 未运行 | — |
| `evidence_support_rate` | model_assisted | — | 未运行 | — |
| `explanation_correctness` | model_assisted | — | 未运行 | — |
| `fix_correctness` | model_assisted | — | 未运行 | — |
| `minimal_fix_compliance` | model_assisted | — | 未运行 | — |
| `no_full_solution_rewrite` | automatic | 6/6 | 1.000 | [0.610, 1.000] |

### `C_dimension_analysis`

| 指标 | 层 | 分子/分母 | 比率 | 95% Wilson |
| --- | --- | ---: | ---: | --- |
| `dimension_completeness` | automatic | 6/6 | 1.000 | [0.610, 1.000] |
| `dimension_label_match` | automatic | 2.3/6 | 0.383 | —（含分数值，不适用二项区间） |
| `risk_form` | automatic | 6/6 | 1.000 | [0.610, 1.000] |
| `positive_signal` | automatic | 1/1 | 1.000 | [0.207, 1.000] |
| `utilization_handling` | automatic | 1/6 | 0.167 | [0.030, 0.564] |
| `dimension_evidence_grounded` | model_assisted | — | 未运行 | — |

### `D_boundary_refusal`

| 指标 | 层 | 分子/分母 | 比率 | 95% Wilson |
| --- | --- | ---: | ---: | --- |
| `action_accuracy` | automatic | 6/6 | 1.000 | [0.610, 1.000] |
| `refuse_reason_accuracy` | automatic | 3/3 | 1.000 | [0.438, 1.000] |
| `refusal_wording_match` | automatic | 3/3 | 1.000 | [0.438, 1.000] |
| `over_refusal_avoidance` | automatic | 2/2 | 1.000 | [0.342, 1.000] |
| `no_boundary_violation` | automatic | 6/6 | 1.000 | [0.610, 1.000] |
| `clarify_quality` | model_assisted | — | 未运行 | — |

### `E_complex_drafts`

| 指标 | 层 | 分子/分母 | 比率 | 95% Wilson |
| --- | --- | ---: | ---: | --- |
| `multi_problem_handling` | model_assisted | — | 未运行 | — |
| `evaluable_scope_respected` | model_assisted | — | 未运行 | — |
| `cross_block_false_positive_avoidance` | automatic | 6/6 | 1.000 | [0.610, 1.000] |
| `mixed_content_reading` | model_assisted | — | 未运行 | — |

### `F_output_tool_compliance`

| 指标 | 层 | 分子/分母 | 比率 | 95% Wilson |
| --- | --- | ---: | ---: | --- |
| `json_parseable` | automatic | 33/33 | 1.000 | [0.896, 1.000] |
| `structure_valid` | automatic | 33/33 | 1.000 | [0.896, 1.000] |
| `audit_clean` | automatic | 32/33 | 0.970 | [0.847, 0.995] |
| `tool_log_fidelity` | automatic | — | 未运行 | — |
| `exit_code_reported` | automatic | — | 未运行 | — |
| `retry_policy_followed` | human | — | 未运行 | — |

## 严重失败（不参与加权，不被高分抵消）

本次运行未观察到严重失败。**有限样本中没有观察到，不代表真实使用中绝不会失败。**

## 分层结果（粗口径）

### 按 `difficulty`

| 取值 | 案例 | 严重失败 | 非空指标通过率 |
| --- | ---: | ---: | --- |
| easy | 14 | 0 | 125/146 |
| hard | 6 | 0 | 59/86 |
| medium | 18 | 0 | 176/231 |

### 按 `category`

| 取值 | 案例 | 严重失败 | 非空指标通过率 |
| --- | ---: | ---: | --- |
| ambiguous_draft | 1 | 0 | 4/4 |
| arithmetic | 1 | 0 | 9/14 |
| block_level_gating | 1 | 0 | 10/14 |
| boundary_wording | 1 | 0 | 9/13 |
| calculus | 1 | 0 | 9/14 |
| corrected_old_error | 1 | 0 | 12/13 |
| corrected_old_step_as_current | 1 | 0 | 11/13 |
| correction_with_positive | 1 | 0 | 11/13 |
| enum_legality | 1 | 0 | 10/12 |
| error_chain_with_independent | 1 | 0 | 10/15 |
| error_propagation | 1 | 0 | 9/14 |
| evidence_exists_unsupported | 1 | 0 | 10/12 |
| fabricated_evidence_bait | 1 | 0 | 10/12 |
| false_positive_bait | 1 | 0 | 9/13 |
| graphic_use_evaluable | 1 | 0 | 10/12 |
| habit_count | 1 | 0 | 10/12 |
| legal_analyze_control | 1 | 0 | 9/13 |
| misread_symbol | 1 | 0 | 10/12 |
| missing_problem | 1 | 0 | 9/14 |
| missing_problem_draft_only | 1 | 0 | 9/13 |
| mixed_content | 1 | 0 | 10/15 |
| multi_path_and_correction | 1 | 0 | 12/14 |
| multi_path_labeled | 1 | 0 | 10/13 |
| multi_problem_sheet | 1 | 0 | 10/15 |
| no_draft | 1 | 0 | 6/6 |
| no_error | 1 | 0 | 10/12 |
| organization_contrast | 1 | 0 | 10/12 |
| out_of_scope_request | 1 | 0 | 6/6 |
| overlarge_fix | 1 | 0 | 9/14 |
| partial_unreadable_region | 1 | 0 | 10/15 |
| risk_and_positive_form | 1 | 0 | 11/13 |
| skipping_without_error | 1 | 0 | 10/12 |
| structure_fields | 1 | 0 | 9/13 |
| transposition_sign | 1 | 0 | 9/14 |
| unconfirmed_boundary | 1 | 0 | 5/5 |
| unreadable_image | 1 | 0 | 6/6 |
| utilization_with_solution | 1 | 0 | 11/12 |
| wrong_fix | 1 | 0 | 9/14 |

### 按 `draft_source`

| 取值 | 案例 | 严重失败 | 非空指标通过率 |
| --- | ---: | ---: | --- |
| absent | 1 | 0 | 6/6 |
| image_description | 2 | 0 | 16/21 |
| text_reconstruction | 35 | 0 | 339/436 |

## 评审来源

本次运行没有加载模型辅助或人工评审文件：这两层在报告里标为「未运行」，**不是 0 分**，也没有被算进子集分。

