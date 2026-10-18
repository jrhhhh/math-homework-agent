# math-solver 基准报告

- 预测文件：`predictions/fixtures/oracle.json`
- 运行组：`skill_gates`
- 模型：`oracle-fixture`
- 运行 ID：`fixture-oracle-2026-10-18`

## 总分

| 指标 | 数值 |
| --- | ---: |
| 总分 | **100** |
| 答案正确率 | 100%（95% CI 87.94–100） |
| 状态正确率 | 100%（95% CI 87.94–100） |
| 核验诚实率 | 100% |
| 边界路由分 | 100 |
| 案例数 | 32 |
| 严重失败数 | 0 |

## 子集

| 子集 | 案例 | 权重 | 得分 |
| --- | ---: | ---: | ---: |
| `answer_core` | 14 | 45 | 100 |
| `verification_discipline` | 9 | 30 | 100 |
| `status_handling` | 5 | 15 | 100 |
| `boundary_routing` | 4 | 10 | 100 |

## 数据划分

| 划分 | 案例 | 得分 |
| --- | ---: | ---: |
| `development` | 27 | 100 |
| `test` | 5 | 100 |

## 严重失败

无。

## 逐案例

| 案例 | 子集 | 动作 | 得分 | 答案 | 状态 | 核验 | 转交/澄清 | 严重失败 |
| --- | --- | --- | ---: | --- | --- | --- | --- | --- |
| `MATH-01` | `answer_core` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-02` | `answer_core` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-03` | `answer_core` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-04` | `answer_core` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-05` | `answer_core` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-06` | `answer_core` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-07` | `answer_core` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-08` | `answer_core` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-09` | `answer_core` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-10` | `answer_core` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-11` | `answer_core` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-12` | `answer_core` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-13` | `answer_core` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-14` | `answer_core` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-15` | `verification_discipline` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-16` | `verification_discipline` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-17` | `verification_discipline` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-18` | `verification_discipline` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-19` | `verification_discipline` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-20` | `verification_discipline` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-21` | `verification_discipline` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-22` | `verification_discipline` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-23` | `verification_discipline` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-24` | `status_handling` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-25` | `status_handling` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-26` | `status_handling` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-27` | `status_handling` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-28` | `status_handling` | solve | 100 | ✓ | ✓ | ✓ | — | — |
| `MATH-29` | `boundary_routing` | route | 100 | — | — | — | ✓ | — |
| `MATH-30` | `boundary_routing` | route | 100 | — | — | — | ✓ | — |
| `MATH-31` | `boundary_routing` | clarify | 100 | — | — | — | ✓ | — |
| `MATH-32` | `boundary_routing` | clarify | 100 | — | — | — | ✓ | — |

## 读分口径

- 自动层只做结构、答案形式、分支覆盖与措辞检查；**不判断推导是否优雅、方法是否最优**。
- 答案检查面向本基准的固定案例：`value_set`、`interval_set`、`text_forms`、`piecewise`、`empty_set`。
- 严重失败直接把案例记 0，不参与加权抵消。
- 答案正确率与状态正确率单独列出，不应只用总分概括。
- 括号内是 95% Wilson 区间；32 条样本下区间很宽，不要把点估计当作稳定准确率。

