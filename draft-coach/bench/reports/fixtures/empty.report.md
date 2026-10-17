# Draft Coach 版面习惯基准报告

- 基准版本：`1.0.0`
- 生成时间：2026-10-17 21:24:11
- 实验组：`fixture-empty`
- 模型 / 产出方：`fixture:empty`
- run_id：`fixture-empty-2026-10-17`

## 总览

| 指标 | 数值 |
| --- | ---: |
| 加权总分（0–100） | **0.0** |
| 硬门槛通过（无严重失败） | 0 / 24（0） |
| 严重失败 | 24 |
| 评估案例数 | 24 |

## 子集分

| 子集 | 权重 | 案例 | 有分案例 | 子集分 | 严重失败 |
| --- | ---: | ---: | ---: | ---: | ---: |
| layout_core | 40 | 10 | 10 | 0.0 | 10 |
| evidence_discipline | 20 | 5 | 5 | 0.0 | 5 |
| partition | 25 | 5 | 5 | 0.0 | 5 |
| input_modes | 15 | 4 | 4 | 0.0 | 4 |

## 检查项通过率

| 检查 | 通过率 | 分子 / 分母 | 说明 |
| --- | ---: | ---: | --- |
| `action_correct` | 0.0% | 0 / 24 |  |

## 严重失败

| 案例 | 子集 | 代码 | 说明 |
| --- | --- | --- | --- |
| LAY-01 | layout_core | `S_MISSING_PREDICTION` | 案例没有对应的预测输出 |
| LAY-02 | layout_core | `S_MISSING_PREDICTION` | 案例没有对应的预测输出 |
| LAY-03 | layout_core | `S_MISSING_PREDICTION` | 案例没有对应的预测输出 |
| LAY-04 | layout_core | `S_MISSING_PREDICTION` | 案例没有对应的预测输出 |
| LAY-05 | layout_core | `S_MISSING_PREDICTION` | 案例没有对应的预测输出 |
| LAY-06 | layout_core | `S_MISSING_PREDICTION` | 案例没有对应的预测输出 |
| LAY-07 | layout_core | `S_MISSING_PREDICTION` | 案例没有对应的预测输出 |
| LAY-08 | layout_core | `S_MISSING_PREDICTION` | 案例没有对应的预测输出 |
| LAY-09 | layout_core | `S_MISSING_PREDICTION` | 案例没有对应的预测输出 |
| LAY-10 | layout_core | `S_MISSING_PREDICTION` | 案例没有对应的预测输出 |
| EVD-01 | evidence_discipline | `S_MISSING_PREDICTION` | 案例没有对应的预测输出 |
| EVD-02 | evidence_discipline | `S_MISSING_PREDICTION` | 案例没有对应的预测输出 |
| EVD-03 | evidence_discipline | `S_MISSING_PREDICTION` | 案例没有对应的预测输出 |
| EVD-04 | evidence_discipline | `S_MISSING_PREDICTION` | 案例没有对应的预测输出 |
| EVD-05 | evidence_discipline | `S_MISSING_PREDICTION` | 案例没有对应的预测输出 |
| PAR-01 | partition | `S_MISSING_PREDICTION` | 案例没有对应的预测输出 |
| PAR-02 | partition | `S_MISSING_PREDICTION` | 案例没有对应的预测输出 |
| PAR-03 | partition | `S_MISSING_PREDICTION` | 案例没有对应的预测输出 |
| PAR-04 | partition | `S_MISSING_PREDICTION` | 案例没有对应的预测输出 |
| PAR-05 | partition | `S_MISSING_PREDICTION` | 案例没有对应的预测输出 |
| INP-01 | input_modes | `S_MISSING_PREDICTION` | 案例没有对应的预测输出 |
| INP-02 | input_modes | `S_MISSING_PREDICTION` | 案例没有对应的预测输出 |
| INP-03 | input_modes | `S_MISSING_PREDICTION` | 案例没有对应的预测输出 |
| INP-04 | input_modes | `S_MISSING_PREDICTION` | 案例没有对应的预测输出 |

## 案例明细（非满分或有严重失败）

| 案例 | 分数 | 严重失败 |
| --- | ---: | --- |
| LAY-01 | 0.0 | S_MISSING_PREDICTION |
| LAY-02 | 0.0 | S_MISSING_PREDICTION |
| LAY-03 | 0.0 | S_MISSING_PREDICTION |
| LAY-04 | 0.0 | S_MISSING_PREDICTION |
| LAY-05 | 0.0 | S_MISSING_PREDICTION |
| LAY-06 | 0.0 | S_MISSING_PREDICTION |
| LAY-07 | 0.0 | S_MISSING_PREDICTION |
| LAY-08 | 0.0 | S_MISSING_PREDICTION |
| LAY-09 | 0.0 | S_MISSING_PREDICTION |
| LAY-10 | 0.0 | S_MISSING_PREDICTION |
| EVD-01 | 0.0 | S_MISSING_PREDICTION |
| EVD-02 | 0.0 | S_MISSING_PREDICTION |
| EVD-03 | 0.0 | S_MISSING_PREDICTION |
| EVD-04 | 0.0 | S_MISSING_PREDICTION |
| EVD-05 | 0.0 | S_MISSING_PREDICTION |
| PAR-01 | 0.0 | S_MISSING_PREDICTION |
| PAR-02 | 0.0 | S_MISSING_PREDICTION |
| PAR-03 | 0.0 | S_MISSING_PREDICTION |
| PAR-04 | 0.0 | S_MISSING_PREDICTION |
| PAR-05 | 0.0 | S_MISSING_PREDICTION |
| INP-01 | 0.0 | S_MISSING_PREDICTION |
| INP-02 | 0.0 | S_MISSING_PREDICTION |
| INP-03 | 0.0 | S_MISSING_PREDICTION |
| INP-04 | 0.0 | S_MISSING_PREDICTION |

## 覆盖度

- by_subset：layout_core=10、evidence_discipline=5、partition=5、input_modes=4
- by_split：development=16、test=3、validation=5
- by_difficulty：easy=7、hard=7、medium=10
- by_draft_source：image_description=6、text_reconstruction=18
- by_grade_level：初中=4、高中=20
- by_action：None=24

## 分层粗读数

### split

| 层 | 案例 | 案例分均值 | 严重失败案例 |
| --- | ---: | ---: | ---: |
| development | 16 | 0.0 | 16 |
| test | 3 | 0.0 | 3 |
| validation | 5 | 0.0 | 5 |

### difficulty

| 层 | 案例 | 案例分均值 | 严重失败案例 |
| --- | ---: | ---: | ---: |
| easy | 7 | 0.0 | 7 |
| hard | 7 | 0.0 | 7 |
| medium | 10 | 0.0 | 10 |

### draft_source

| 层 | 案例 | 案例分均值 | 严重失败案例 |
| --- | ---: | ---: | ---: |
| image_description | 6 | 0.0 | 6 |
| text_reconstruction | 18 | 0.0 | 18 |

### grade_level

| 层 | 案例 | 案例分均值 | 严重失败案例 |
| --- | ---: | ---: | ---: |
| 初中 | 4 | 0.0 | 4 |
| 高中 | 20 | 0.0 | 20 |

## 这套分不代表什么

- 两道门都不验数学；本技能也不判断计算对错。结构/措辞通过不等于版面观察属实。
- 证据锚点只证明「卡片引用了草稿里出现过的位置或痕迹」，不证明那处观察一定正确。
- 24 条案例是合成的文字还原/文字描述，不是随机抽样的真实学生草稿；图片案例没有真实图片，只有版面文字描述。
- 自动层不评价「这条习惯是否真的适合这个学生」；该问题只走人工层（`engine/human_review.py`）。
- 权重未经试运行校准；覆盖薄的子集即使得高分也不能外推。
