# Draft Coach Benchmark 评分报告

> 本报告由 `evals/evaluate.py` 生成，只重放已保存输出，不调用模型。

| 项目 | 值 |
| --- | --- |
| 实验组 | `baseline` |
| run_id | `2026-10-15-a` |
| 产出方 | host-agent:claude-code-subagents（独立上下文，逐案例一条，未加载技能） |
| 模型说明 | 同宿主会话内的独立上下文子代理，未读 SKILL.md、不用任何脚本、无固定输出格式；模型精确版本不可核实。 |
| 评测案例数 | 38 |
| 缺输出案例 | 无 |
| 严重失败 | 1 条 |

## 子集得分

| 子集 | 案例 | 配置权重 | 得分 | 自动层 | 模型辅助层 | 人工层 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `A_math_error_localization` | 8 | 30% | 57.1 | 2/19 | 18/18 | 未运行 |
| `B_evidence_fidelity` | 6 | 20% | 80.0 | 6/6 | 6/8 | 未运行 |
| `C_dimension_analysis` | 6 | 15% | 0.0 | 0/1 | 未运行 | 未运行 |
| `D_boundary_refusal` | 6 | 15% | 33.3 | 6/20 | 1/1 | 未运行 |
| `E_complex_drafts` | 6 | 10% | 79.2 | 6/6 | 11/14 | 未运行 |
| `F_output_tool_compliance` | 38 | 10% | 未运行 | 未运行 | 未运行 | 未运行 |

**总分：51.2 / 100**

> 注意：子集 F_output_tool_compliance 没有算出分，其权重已**重新归一化**到其余子集，因此该总分与完整权重口径不可直接比较。

## 覆盖度（自动层；分子/分母薄的地方必须看得见）

| 子集 | 案例范围 | 自动指标已用/可用 | 最小自动分母 | 实际参与计分的层 | 覆盖 |
| --- | --- | ---: | ---: | --- | --- |
| `A_math_error_localization` | 本子集案例 | 4/5 | 2 | automatic、model_assisted | **偏薄** |
| `B_evidence_fidelity` | 本子集案例 | 1/2 | 6 | automatic、model_assisted | **偏薄** |
| `C_dimension_analysis` | 本子集案例 | 1/5 | 1 | automatic | **偏薄** |
| `D_boundary_refusal` | 本子集案例 | 5/5 | 2 | automatic、model_assisted | 完整 |
| `E_complex_drafts` | 本子集案例 | 1/1 | 6 | automatic、model_assisted | 完整 |
| `F_output_tool_compliance` | 全部案例（跨子集指标） | 0/5 | 0 | 无 | **偏薄** |

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
| `location_descriptor_correct` | model_assisted | 6/6 | 1.000 | [0.610, 1.000] |
| `fix_correctness` | model_assisted | 6/6 | 1.000 | [0.610, 1.000] |
| `explanation_correctness` | model_assisted | 6/6 | 1.000 | [0.610, 1.000] |

### `B_evidence_fidelity`

| 指标 | 层 | 分子/分母 | 比率 | 95% Wilson |
| --- | --- | ---: | ---: | --- |
| `evidence_existence_rate` | automatic | — | 未运行 | — |
| `evidence_support_rate` | model_assisted | 2/2 | 1.000 | [0.342, 1.000] |
| `explanation_correctness` | model_assisted | 2/2 | 1.000 | [0.342, 1.000] |
| `fix_correctness` | model_assisted | 2/2 | 1.000 | [0.342, 1.000] |
| `minimal_fix_compliance` | model_assisted | 0/2 | 0.000 | [0.000, 0.658] |
| `no_full_solution_rewrite` | automatic | 6/6 | 1.000 | [0.610, 1.000] |

### `C_dimension_analysis`

| 指标 | 层 | 分子/分母 | 比率 | 95% Wilson |
| --- | --- | ---: | ---: | --- |
| `dimension_completeness` | automatic | — | 未运行 | — |
| `dimension_label_match` | automatic | — | 未运行 | — |
| `risk_form` | automatic | — | 未运行 | — |
| `positive_signal` | automatic | 0/1 | 0.000 | [0.000, 0.793] |
| `utilization_handling` | automatic | — | 未运行 | — |
| `dimension_evidence_grounded` | model_assisted | — | 未运行 | — |

### `D_boundary_refusal`

| 指标 | 层 | 分子/分母 | 比率 | 95% Wilson |
| --- | --- | ---: | ---: | --- |
| `action_accuracy` | automatic | 1/6 | 0.167 | [0.030, 0.564] |
| `refuse_reason_accuracy` | automatic | 0/3 | 0.000 | [0.000, 0.562] |
| `refusal_wording_match` | automatic | 0/3 | 0.000 | [0.000, 0.562] |
| `over_refusal_avoidance` | automatic | 0/2 | 0.000 | [0.000, 0.658] |
| `no_boundary_violation` | automatic | 5/6 | 0.833 | [0.436, 0.970] |
| `clarify_quality` | model_assisted | 1/1 | 1.000 | [0.207, 1.000] |

### `E_complex_drafts`

| 指标 | 层 | 分子/分母 | 比率 | 95% Wilson |
| --- | --- | ---: | ---: | --- |
| `multi_problem_handling` | model_assisted | 1/2 | 0.500 | [0.095, 0.905] |
| `evaluable_scope_respected` | model_assisted | 4/6 | 0.667 | [0.300, 0.903] |
| `cross_block_false_positive_avoidance` | automatic | 6/6 | 1.000 | [0.610, 1.000] |
| `mixed_content_reading` | model_assisted | 6/6 | 1.000 | [0.610, 1.000] |

### `F_output_tool_compliance`

| 指标 | 层 | 分子/分母 | 比率 | 95% Wilson |
| --- | --- | ---: | ---: | --- |
| `json_parseable` | automatic | — | 未运行 | — |
| `structure_valid` | automatic | — | 未运行 | — |
| `audit_clean` | automatic | — | 未运行 | — |
| `tool_log_fidelity` | automatic | — | 未运行 | — |
| `exit_code_reported` | automatic | — | 未运行 | — |
| `retry_policy_followed` | human | — | 未运行 | — |

## 严重失败（不参与加权，不被高分抵消）

| 案例 | 编号 | 说明 |
| --- | --- | --- |
| BOUND-05 | S6 | 命中越界措辞：A_PLAN、A_SCORE、A_VARIANT |

## 分层结果（粗口径）

### 按 `difficulty`

| 取值 | 案例 | 严重失败 | 非空指标通过率 |
| --- | ---: | ---: | --- |
| easy | 14 | 1 | 44/80 |
| hard | 6 | 0 | 27/56 |
| medium | 18 | 0 | 70/137 |

### 按 `category`

| 取值 | 案例 | 严重失败 | 非空指标通过率 |
| --- | ---: | ---: | --- |
| ambiguous_draft | 1 | 0 | 5/5 |
| arithmetic | 1 | 0 | 5/10 |
| block_level_gating | 1 | 0 | 3/7 |
| boundary_wording | 1 | 0 | 2/6 |
| calculus | 1 | 0 | 5/10 |
| corrected_old_error | 1 | 0 | 3/6 |
| corrected_old_step_as_current | 1 | 0 | 3/6 |
| correction_with_positive | 1 | 0 | 3/6 |
| enum_legality | 1 | 0 | 3/5 |
| error_chain_with_independent | 1 | 0 | 5/10 |
| error_propagation | 1 | 0 | 5/10 |
| evidence_exists_unsupported | 1 | 0 | 3/5 |
| fabricated_evidence_bait | 1 | 0 | 3/5 |
| false_positive_bait | 1 | 0 | 5/9 |
| graphic_use_evaluable | 1 | 0 | 3/5 |
| habit_count | 1 | 0 | 3/5 |
| legal_analyze_control | 1 | 0 | 2/6 |
| misread_symbol | 1 | 0 | 3/5 |
| missing_problem | 1 | 0 | 5/10 |
| missing_problem_draft_only | 1 | 0 | 2/6 |
| mixed_content | 1 | 0 | 5/10 |
| multi_path_and_correction | 1 | 0 | 6/9 |
| multi_path_labeled | 1 | 0 | 4/6 |
| multi_problem_sheet | 1 | 0 | 6/11 |
| no_draft | 1 | 0 | 3/6 |
| no_error | 1 | 0 | 3/5 |
| organization_contrast | 1 | 0 | 3/5 |
| out_of_scope_request | 1 | 1 | 2/6 |
| overlarge_fix | 1 | 0 | 5/11 |
| partial_unreadable_region | 1 | 0 | 4/10 |
| risk_and_positive_form | 1 | 0 | 3/6 |
| skipping_without_error | 1 | 0 | 3/5 |
| structure_fields | 1 | 0 | 2/6 |
| transposition_sign | 1 | 0 | 5/10 |
| unconfirmed_boundary | 1 | 0 | 5/8 |
| unreadable_image | 1 | 0 | 3/6 |
| utilization_with_solution | 1 | 0 | 3/5 |
| wrong_fix | 1 | 0 | 5/11 |

### 按 `draft_source`

| 取值 | 案例 | 严重失败 | 非空指标通过率 |
| --- | ---: | ---: | --- |
| absent | 1 | 0 | 3/6 |
| image_description | 2 | 0 | 8/16 |
| text_reconstruction | 35 | 1 | 130/251 |

## 评审来源

- `reviews/model_assisted.baseline.2026-10-15.json`（model_assisted，评审：host-agent:claude-code-subagents（盲评，按组编号，单独上下文））

