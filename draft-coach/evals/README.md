# evals/ —— Draft Coach 的评测与回归

为 [Draft Coach 技能](../SKILL.md)（草稿检查教练）建的评测子系统。行为依据只有一份：`../SKILL.md`；**评测不修改技能的行为定义**。

纯 Python 标准库，无第三方运行依赖。**没有配置任何模型 API**：`evaluate.py` 不会调用模型，它读取已保存的输出、重放技能自己的两道门、算分、出报告。

## 当前状态（先读这一段）

| 项目 | 状态 |
| --- | --- |
| 案例集 | **38 条**（A 8 / B 6 / C 6 / D 6 / E 6 / F 6），全部通过结构、锚点自洽、两份文件对齐与防泄漏校验 |
| 评测器与报告 | 已实现并跑通（85 项单元与端到端测试全过） |
| 自动层指标 | 已实现，含 4 条可自动判定的严重失败检测 |
| 模型辅助层 / 人工层 | **接口已就绪，未运行**（没有评审文件；接口见 `engine/human_review.py`） |
| baseline / skill / skill_gates 三组真实模型输出 | **未运行**（无模型 API，需要宿主产出） |
| 留出集（`split: test`） | **0 条**，理由见 [HOLDOUT.md](HOLDOUT.md) |
| `S3` 图像歧义硬判、`retry_policy_followed` | **未运行**（需要图片案例 / 多轮 transcript） |

已跑过的是**夹具**（`predictions/fixtures/`，产出方标为 `fixture:...`，报告里带「不是模型运行结果」警告）。它们证明流程跑得通、该抓的抓得住，**不构成任何模型的成绩**。

## 快速开始

```bash
cd draft-coach/evals

# 1) 校验案例与标准答案：结构 + 锚点自洽 + 两文件对齐 + 防泄漏
python3 engine/schema_check.py

# 2) 跑测试
python3 -m unittest discover -s tests -p 'test_*.py'

# 3) 生成夹具（不是模型输出），跑通评测流程
python3 make_fixture_predictions.py --mode oracle --arm skill_gates \
    --out predictions/fixtures/oracle.skill_gates.json
python3 evaluate.py --predictions predictions/fixtures/oracle.skill_gates.json \
    --out reports/fixtures/oracle.skill_gates.report.json \
    --markdown reports/fixtures/oracle.skill_gates.report.md

# 4) 导出人工 / 模型辅助评审表
python3 engine/human_review.py export --layer human --arm skill_gates --out reviews/human.template.json
```

Windows 上 `python3` 可能是应用商店占位程序会静默失败，用可用的解释器（本机为 `"D:/Program Files/anaconda3/python.exe"`）。

## 数据长什么样

案例与标准答案**分两个文件**，按 `case_id` 合并。这样写案例的人拿 `cases.jsonl` 就能造输入，标注的人拿 `ground_truth.jsonl` 独立填答案，不必看到彼此的中间结果。

```
cases.jsonl         每行：case_id / template_id / subset / split / category / difficulty /
                    grade_level / input / expected_action / refuse_reason / severity /
                    provenance / metrics
ground_truth.jsonl  每行：case_id / gold_errors / gold_correct_steps / gold_dimensions /
                    expected_behaviors / forbidden_behaviors / evaluable_scope /
                    unevaluable_scope / notes
```

两份文件的 `case_id` 必须同集同序；少了答案行报 `E_GT_MISSING`，多了答案行报 `E_GT_ORPHAN`。

## 六个子集

| 子集 | 本批 | 正式版目标 | 评什么 |
| --- | ---: | ---: | --- |
| A 数学错误定位 | 8 | 100 | Precision / Recall / 定位 / 无错识别 / 传播识别 |
| B 证据忠实度 | 6 | 60 | 证据存在率、证据支持率、解释与改法、最小修改 |
| C 六维习惯分析 | 6 | 60 | 六维齐全、标签、风险句形式、积极信号、利用率 |
| D 输入边界与拒绝 | 6 | 50 | 动作正确性、拒绝理由、误拒、越界 |
| E 复杂草稿场景 | 6 | 60 | 多题分块、可判范围、跨块假错、混排读取 |
| F 输出与工具合规 | 6 | 50 | 结构、审计、**工具记录真实性**、退出码 |

**目标是目标，不是已完成量**；实际条数由校验器在运行时统计。分布：development 25 / validation 13；33 条预期产出卡片，3 条拒绝、2 条追问；难度 easy 14 / medium 18 / hard 6；共 33 条标准错误、21 条「草稿无错」。

## 评分怎么算

两层，**分开陈述、不混算**：

1. **硬门槛**：严重失败（`S1` 编造证据、`S2` 把对判成错、`S3` 图像歧义硬判、`S4` 无草稿却伪造分析、`S5` 伪造工具执行记录、`S6` 越界行为）**单独统计，不被任何高分抵消**。
2. **加权分**：六子集按 A 30% / B 20% / C 15% / D 15% / E 10% / F 10% 归一化到 0–100 后加权求和。

指标分三层：**自动**（确定性、重跑一致）、**模型辅助**（独立上下文评审，不是 ground truth）、**人工**（`human_review.py` 回读）。未运行的层记为「未运行」，**不是 0 分**，也不进分母。

细则与全部公式见 [docs/DESIGN.md](docs/DESIGN.md)（含 §3.2 的计数规则：`propagated` 与 `must_report=false` 的条目不进 Precision/Recall，避免重复计数）。

## 目录

```text
cases.jsonl / ground_truth.jsonl  案例与标准答案
evaluate.py                       主入口：加载 → 重放两道门 → 算分 → 出报告
make_fixture_predictions.py       生成夹具（不是模型输出）
config.json                       权重、子集→指标、计数规则、严重失败分类、门脚本路径
engine/cases.py                   两份 jsonl 的加载与合并
engine/metrics.py                 自动指标（常量取自 ../scripts/_rules.py，不重抄）
engine/gate_replay.py             重放 skills 的两道门，检测伪造工具记录
engine/scoring.py                 子集分、总分、Wilson 区间、覆盖度、分层
engine/schema_check.py            案例与标准答案的校验
engine/human_review.py            人工 / 模型辅助评审的导出与回读
schemas/                          case.schema.json、prediction.schema.json
docs/                             DESIGN / ANNOTATION_GUIDE / RULE_TO_CASE_MAP / FINDINGS
tests/                            85 项单元与端到端测试
predictions/                      三组实验输出（当前只有 fixtures/）
reports/                          报告与报告模板
reviews/                          评审文件（当前为空 = 两层未运行）
HOLDOUT.md                        留出集说明（本批 0 条）
```

## 三个实验组

| 组 | 加载 SKILL.md | 跑门脚本 |
| --- | --- | --- |
| `baseline` | 否 | 否 |
| `skill` | 是 | 否 |
| `skill_gates` | 是 | **是**（记录真实退出码） |

`evaluate.py` 会把 `card` 重新喂给 `../scripts/validate_output.py` 与 `../scripts/audit_output.py`，比对 `tool_log` 里声称的退出码：**对不上就是严重失败 `S5`（伪造工具执行记录）**。契约见 [predictions/README.md](predictions/README.md)。

## 这套评测做不到什么

- **两道门都不验数学。** `validate` 只查结构，`audit` 只查措辞与「证据在不在草稿里」。结构通过不等于「这处算错了」判得对。数学正确性只走模型辅助 / 人工层，**本批两层都未运行**。
- **自动指标里的锚点匹配只证明「引用的是草稿那处」**，不证明「那处真的错了」。所以 `evidence_support_rate`、`explanation_correctness`、`fix_correctness` 一律不自动给分。
- **38 条是合成材料**（`draft_source` 多为文字还原），不是真实学生草稿，也不是随机抽样。
- **没有人类标注者参与**，因此不声称标注一致性；[标注指南 §10](docs/ANNOTATION_GUIDE.md) 只给出双人标注与仲裁的流程设计。
- **权重未经试运行校准。**
- **覆盖偏薄的地方分数照样会是 100 分**：报告里的覆盖度表必须与分数一起读（原因见 [FINDINGS F4](docs/FINDINGS.md)）。
- 自动指标的四条严重失败检测（S1/S2/S4/S5）都有真实触发的证据（夹具里触发过）；`S3` 与 `S6` 的人工部分未运行。
