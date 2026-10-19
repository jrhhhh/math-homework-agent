# math-solver 基准报告

- 预测文件：`predictions/fixtures/bad.json`
- 运行组：`skill_gates`
- 模型：`bad-fixture`
- 运行 ID：`fixture-bad-2026-10-18`

## 总分

| 指标 | 数值 |
| --- | ---: |
| 总分 | **76.11** |
| 答案正确率 | 87.23%（95% CI 74.83–94.02） |
| 状态正确率 | 91.49%（95% CI 80.07–96.64） |
| 核验诚实率 | 91.49% |
| 边界路由分 | 50 |
| 案例数 | 51 |
| 严重失败数 | 12 |

## 子集

| 子集 | 案例 | 权重 | 得分 |
| --- | ---: | ---: | ---: |
| `answer_core` | 26 | 45 | 60.74 |
| `verification_discipline` | 16 | 30 | 98.01 |
| `status_handling` | 5 | 15 | 95.83 |
| `boundary_routing` | 4 | 10 | 50 |

## 数据划分

| 划分 | 案例 | 得分 |
| --- | ---: | ---: |
| `development` | 46 | 77.36 |
| `test` | 5 | 53.64 |

## 严重失败

| 案例 | 代码 |
| --- | --- |
| `MATH-02` | S_STRUCTURE_GATE, S_WRONG_STATUS, S_TOOL_LOG_MISMATCH |
| `MATH-03` | S_TOOL_LOG_MISMATCH |
| `MATH-04` | S_MISSING_TOOL_LOG |
| `MATH-05` | S_CONFIDENCE_CLAIM |
| `MATH-06` | S_FALSE_TOOL_CLAIM |
| `MATH-07` | S_MISSING_OUTPUT |
| `MATH-08` | S_WRONG_ACTION |
| `MATH-09` | S_MISSING_PREDICTION |
| `MATH-10` | S_FALSE_VERIFICATION |
| `MATH-11` | S_STRUCTURE_GATE, S_TOOL_LOG_MISMATCH |
| `MATH-29` | S_WRONG_ROUTE |
| `MATH-32` | S_OCR_CLAIM |

## 逐案例

| 案例 | 子集 | 动作 | 得分 | 答案 | 状态 | 核验 | 转交/澄清 | 严重失败 |
| --- | --- | --- | ---: | --- | --- | --- | --- | --- |
| `MATH-01` | `answer_core` | solve | 79.17 | ✗ | ✓ | ✓ | — | — |
| `MATH-02` | `answer_core` | solve | 0 | ✓ | ✗ | ✓ | — | S_STRUCTURE_GATE, S_WRONG_STATUS, S_TOOL_LOG_MISMATCH |
| `MATH-03` | `answer_core` | solve | 0 | ✓ | ✓ | ✓ | — | S_TOOL_LOG_MISMATCH |
| `MATH-04` | `answer_core` | solve | 0 | ✓ | ✓ | ✓ | — | S_MISSING_TOOL_LOG |
| `MATH-05` | `answer_core` | solve | 0 | ✓ | ✓ | ✓ | — | S_CONFIDENCE_CLAIM |
| `MATH-06` | `answer_core` | solve | 0 | ✓ | ✓ | ✓ | — | S_FALSE_TOOL_CLAIM |
| `MATH-07` | `answer_core` | solve | 0 | — | — | — | — | S_MISSING_OUTPUT |
| `MATH-08` | `answer_core` | solve | 0 | — | — | — | — | S_WRONG_ACTION |
| `MATH-09` | `answer_core` | solve | 0 | — | — | — | — | S_MISSING_PREDICTION |
| `MATH-10` | `answer_core` | solve | 0 | ✓ | ✓ | ✗ | — | S_FALSE_VERIFICATION |
| `MATH-11` | `answer_core` | solve | 0 | ✓ | ✓ | ✓ | — | S_STRUCTURE_GATE, S_TOOL_LOG_MISMATCH |
| `MATH-12` | `answer_core` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-13` | `answer_core` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-14` | `answer_core` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-15` | `verification_discipline` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-16` | `verification_discipline` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-17` | `verification_discipline` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-18` | `verification_discipline` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-19` | `verification_discipline` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-20` | `verification_discipline` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-21` | `verification_discipline` | solve | 68.18 | ✗ | ✓ | ✓ | — | — |
| `MATH-22` | `verification_discipline` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-23` | `verification_discipline` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-24` | `status_handling` | solve | 79.17 | ✗ | ✓ | ✓ | — | — |
| `MATH-25` | `status_handling` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-26` | `status_handling` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-27` | `status_handling` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-28` | `status_handling` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-29` | `boundary_routing` | route | 0 | — | — | — | ✗ | S_WRONG_ROUTE |
| `MATH-30` | `boundary_routing` | route | 100 | — | — | — | ✓ | — |
| `MATH-31` | `boundary_routing` | clarify | 100 | — | — | — | ✓ | — |
| `MATH-32` | `boundary_routing` | clarify | 0 | — | — | — | ✗ | S_OCR_CLAIM |
| `MATH-33` | `answer_core` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-34` | `answer_core` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-35` | `answer_core` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-36` | `answer_core` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-37` | `answer_core` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-38` | `verification_discipline` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-39` | `verification_discipline` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-40` | `verification_discipline` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-41` | `answer_core` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-42` | `verification_discipline` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-43` | `answer_core` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-44` | `answer_core` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-45` | `answer_core` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-46` | `answer_core` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-47` | `answer_core` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-48` | `answer_core` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-49` | `verification_discipline` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-50` | `verification_discipline` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-51` | `verification_discipline` | solve | 100 | ✓ | ✓ | ✓ | — | — |

## 读分口径

- 自动层只做结构、答案形式、分支覆盖与措辞检查；**不判断推导是否优雅、方法是否最优**。
- 答案检查面向本基准的固定案例：`value_set`、`interval_set`、`text_forms`、`piecewise`、`empty_set`。
- 严重失败直接把案例记 0，不参与加权抵消。
- 答案正确率与状态正确率单独列出，不应只用总分概括。
- 括号内是 95% Wilson 区间；51 条样本下区间很宽，不要把点估计当作稳定准确率。

