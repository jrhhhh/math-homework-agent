# Draft Coach Benchmark 评分报告

> 本报告由 `evals/evaluate.py` 生成，只重放已保存输出，不调用模型。

| 项目 | 值 |
| --- | --- |
| 实验组 | `skill_gates` |
| run_id | `2026-10-15-a` |
| 产出方 | host-agent:claude-code-subagents（独立上下文，逐案例一条） |
| 模型说明 | 同宿主会话内的独立上下文子代理逐案例产出；模型精确版本不可核实，不作可逐字复现的声称。 |
| 评测案例数 | 38 |
| 缺输出案例 | 无 |
| 严重失败 | 1 条 |

## 子集得分

| 子集 | 案例 | 配置权重 | 得分 | 自动层 | 模型辅助层 | 人工层 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `A_math_error_localization` | 8 | 30% | 100.0 | 25/25 | 18/18 | 未运行 |
| `B_evidence_fidelity` | 6 | 20% | 100.0 | 8/8 | 8/8 | 未运行 |
| `C_dimension_analysis` | 6 | 15% | 98.9 | 24.6/25 | 6/6 | 未运行 |
| `D_boundary_refusal` | 6 | 15% | 100.0 | 20/20 | 1/1 | 未运行 |
| `E_complex_drafts` | 6 | 10% | 95.8 | 5/6 | 14/14 | 未运行 |
| `F_output_tool_compliance` | 38 | 10% | 99.4 | 169/170 | 未运行 | 未运行 |

**总分：99.4 / 100**

## 覆盖度（自动层；分子/分母薄的地方必须看得见）

| 子集 | 案例范围 | 自动指标已用/可用 | 最小自动分母 | 实际参与计分的层 | 覆盖 |
| --- | --- | ---: | ---: | --- | --- |
| `A_math_error_localization` | 本子集案例 | 5/5 | 2 | automatic、model_assisted | 完整 |
| `B_evidence_fidelity` | 本子集案例 | 2/2 | 2 | automatic、model_assisted | 完整 |
| `C_dimension_analysis` | 本子集案例 | 5/5 | 1 | automatic、model_assisted | 完整 |
| `D_boundary_refusal` | 本子集案例 | 5/5 | 2 | automatic、model_assisted | 完整 |
| `E_complex_drafts` | 本子集案例 | 1/1 | 6 | automatic、model_assisted | 完整 |
| `F_output_tool_compliance` | 全部案例（跨子集指标） | 5/5 | 34 | automatic | 完整 |

> 自动层覆盖偏薄时分数仍可能是 100 分，必须连着分子分母一起读。最典型的情形：「什么错都不报」的空答案在「证据忠实度」上没有证据可判不忠实，于是拿到满分——它真正的失分在「数学错误定位」的 Recall 上。
>
> 模型辅助层与人工层未加载时记为「未运行」，**不是 0 分**，也不参与子集分；这也是「实际参与计分的层」一列存在的原因。

## 指标明细（分子/分母，不允许只给比率）

### `A_math_error_localization`

| 指标 | 层 | 分子/分母 | 比率 | 95% Wilson |
| --- | --- | ---: | ---: | --- |
| `error_precision` | automatic | 6/6 | 1.000 | [0.610, 1.000] |
| `error_recall` | automatic | 6/6 | 1.000 | [0.610, 1.000] |
| `error_localization` | automatic | 6/6 | 1.000 | [0.610, 1.000] |
| `no_error_identification` | automatic | 2/2 | 1.000 | [0.342, 1.000] |
| `propagation_quality` | automatic | 5/5 | 1.000 | [0.566, 1.000] |
| `location_descriptor_correct` | model_assisted | 6/6 | 1.000 | [0.610, 1.000] |
| `fix_correctness` | model_assisted | 6/6 | 1.000 | [0.610, 1.000] |
| `explanation_correctness` | model_assisted | 6/6 | 1.000 | [0.610, 1.000] |

### `B_evidence_fidelity`

| 指标 | 层 | 分子/分母 | 比率 | 95% Wilson |
| --- | --- | ---: | ---: | --- |
| `evidence_existence_rate` | automatic | 2/2 | 1.000 | [0.342, 1.000] |
| `evidence_support_rate` | model_assisted | 2/2 | 1.000 | [0.342, 1.000] |
| `explanation_correctness` | model_assisted | 2/2 | 1.000 | [0.342, 1.000] |
| `fix_correctness` | model_assisted | 2/2 | 1.000 | [0.342, 1.000] |
| `minimal_fix_compliance` | model_assisted | 2/2 | 1.000 | [0.342, 1.000] |
| `no_full_solution_rewrite` | automatic | 6/6 | 1.000 | [0.610, 1.000] |

### `C_dimension_analysis`

| 指标 | 层 | 分子/分母 | 比率 | 95% Wilson |
| --- | --- | ---: | ---: | --- |
| `dimension_completeness` | automatic | 6/6 | 1.000 | [0.610, 1.000] |
| `dimension_label_match` | automatic | 5.6/6 | 0.933 | —（含分数值，不适用二项区间） |
| `risk_form` | automatic | 6/6 | 1.000 | [0.610, 1.000] |
| `positive_signal` | automatic | 1/1 | 1.000 | [0.207, 1.000] |
| `utilization_handling` | automatic | 6/6 | 1.000 | [0.610, 1.000] |
| `dimension_evidence_grounded` | model_assisted | 6/6 | 1.000 | [0.610, 1.000] |

### `D_boundary_refusal`

| 指标 | 层 | 分子/分母 | 比率 | 95% Wilson |
| --- | --- | ---: | ---: | --- |
| `action_accuracy` | automatic | 6/6 | 1.000 | [0.610, 1.000] |
| `refuse_reason_accuracy` | automatic | 3/3 | 1.000 | [0.438, 1.000] |
| `refusal_wording_match` | automatic | 3/3 | 1.000 | [0.438, 1.000] |
| `over_refusal_avoidance` | automatic | 2/2 | 1.000 | [0.342, 1.000] |
| `no_boundary_violation` | automatic | 6/6 | 1.000 | [0.610, 1.000] |
| `clarify_quality` | model_assisted | 1/1 | 1.000 | [0.207, 1.000] |

### `E_complex_drafts`

| 指标 | 层 | 分子/分母 | 比率 | 95% Wilson |
| --- | --- | ---: | ---: | --- |
| `multi_problem_handling` | model_assisted | 2/2 | 1.000 | [0.342, 1.000] |
| `evaluable_scope_respected` | model_assisted | 6/6 | 1.000 | [0.610, 1.000] |
| `cross_block_false_positive_avoidance` | automatic | 5/6 | 0.833 | [0.436, 0.970] |
| `mixed_content_reading` | model_assisted | 6/6 | 1.000 | [0.610, 1.000] |

### `F_output_tool_compliance`

| 指标 | 层 | 分子/分母 | 比率 | 95% Wilson |
| --- | --- | ---: | ---: | --- |
| `json_parseable` | automatic | 34/34 | 1.000 | [0.898, 1.000] |
| `structure_valid` | automatic | 34/34 | 1.000 | [0.898, 1.000] |
| `audit_clean` | automatic | 33/34 | 0.971 | [0.851, 0.995] |
| `tool_log_fidelity` | automatic | 34/34 | 1.000 | [0.898, 1.000] |
| `exit_code_reported` | automatic | 34/34 | 1.000 | [0.898, 1.000] |
| `retry_policy_followed` | human | — | 未运行 | — |

## 严重失败（不参与加权，不被高分抵消）

| 案例 | 编号 | 说明 |
| --- | --- | --- |
| CPLX-03 | S2 | 把正确步骤 '(x-2.5)^2=0.25' 报成了错误 |

## 分层结果（粗口径）

### 按 `difficulty`

| 取值 | 案例 | 严重失败 | 非空指标通过率 |
| --- | ---: | ---: | --- |
| easy | 14 | 0 | 177/178 |
| hard | 6 | 0 | 120/122 |
| medium | 18 | 1 | 311/320 |

### 按 `category`

| 取值 | 案例 | 严重失败 | 非空指标通过率 |
| --- | ---: | ---: | --- |
| ambiguous_draft | 1 | 0 | 5/5 |
| arithmetic | 1 | 0 | 21/21 |
| block_level_gating | 1 | 0 | 17/18 |
| boundary_wording | 1 | 0 | 17/17 |
| calculus | 1 | 0 | 20/21 |
| corrected_old_error | 1 | 0 | 14/15 |
| corrected_old_step_as_current | 1 | 0 | 14/15 |
| correction_with_positive | 1 | 0 | 15/16 |
| enum_legality | 1 | 0 | 13/14 |
| error_chain_with_independent | 1 | 0 | 20/21 |
| error_propagation | 1 | 0 | 20/21 |
| evidence_exists_unsupported | 1 | 0 | 13/14 |
| fabricated_evidence_bait | 1 | 0 | 13/14 |
| false_positive_bait | 1 | 0 | 19/20 |
| graphic_use_evaluable | 1 | 0 | 15/15 |
| habit_count | 1 | 0 | 14/14 |
| legal_analyze_control | 1 | 0 | 16/17 |
| misread_symbol | 1 | 0 | 13/14 |
| missing_problem | 1 | 0 | 20/21 |
| missing_problem_draft_only | 1 | 0 | 17/17 |
| mixed_content | 1 | 0 | 20/21 |
| multi_path_and_correction | 1 | 1 | 16/20 |
| multi_path_labeled | 1 | 0 | 14/16 |
| multi_problem_sheet | 1 | 0 | 21/22 |
| no_draft | 1 | 0 | 6/6 |
| no_error | 1 | 0 | 13/14 |
| organization_contrast | 1 | 0 | 15/15 |
| out_of_scope_request | 1 | 0 | 6/6 |
| overlarge_fix | 1 | 0 | 22/22 |
| partial_unreadable_region | 1 | 0 | 20/21 |
| risk_and_positive_form | 1 | 0 | 14/15 |
| skipping_without_error | 1 | 0 | 15/15 |
| structure_fields | 1 | 0 | 16/17 |
| transposition_sign | 1 | 0 | 20/21 |
| unconfirmed_boundary | 1 | 0 | 15/16 |
| unreadable_image | 1 | 0 | 6/6 |
| utilization_with_solution | 1 | 0 | 15/15 |
| wrong_fix | 1 | 0 | 22/22 |

### 按 `draft_source`

| 取值 | 案例 | 严重失败 | 非空指标通过率 |
| --- | ---: | ---: | --- |
| absent | 1 | 0 | 6/6 |
| image_description | 2 | 0 | 26/27 |
| text_reconstruction | 35 | 1 | 576/587 |

## 评审来源

- `reviews/model_assisted.skill_gates.2026-10-15.json`（model_assisted，评审：host-agent:claude-code-subagents（盲评，按组编号，单独上下文））

