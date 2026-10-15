# 真实模型运行记录：draft-coach benchmark（2026-10-15）

本文件记录**本仓库第一次用真实模型输出跑这套 benchmark**的过程、读数与已知缺陷。
在此之前 `predictions/` 里只有夹具，三组实验在报告里一律标「未运行」。

## 跑了什么

| 项目 | 值 |
| --- | --- |
| 日期 | 2026-10-15 |
| 实验组 | `baseline`（不加载技能）、`skill_gates`（加载 `SKILL.md` 并真跑两道门） |
| 案例 | 全部 38 条（development 25 / validation 13，无留出集） |
| 每组运行次数 | **1 次**（`runs_per_condition = 1`） |
| 产出方 | 同宿主会话内的**独立上下文子代理**，一条案例一个上下文 |
| 评审方（模型辅助层） | 另一批独立上下文子代理，按组编号分发盲评包 |
| 原料 | `inputs/`（38 份，只含 `prompt`/`problem`/`draft`/`final_solution`/`draft_source`/`grade_level`/`audit_draft`，**不含 `expected_action`、不含任何标注**） |

产出代理被明令**不许读** `draft-coach/evals/` 下任何文件、`tests/behavior-evaluation/`、
以及别人的输入文件；`baseline` 组另外不许读 `draft-coach/` 全目录。这样做的理由见
[protocol.json](../../../../tests/behavior-evaluation/draft-coach-2026-10-15/protocol.json)
里那套「同模型 + 独立上下文」的做法：被评分者不该预先看过评分器。

## 结果

### 总分（权重 A30/B20/C15/D15/E10/F10）

| 组 | 总分 | 严重失败 | 说明 |
| --- | ---: | ---: | --- |
| `skill_gates` | **99.36 / 100** | 2 条 | 六个子集全部参与计分，未重新归一化 |
| `baseline` | **51.18 / 100** | 1 条 | F 子集无任何指标可算 → **权重已重新归一化**，与完整权重口径不可直接比较 |

### 子集与关键指标

| 子集 | skill_gates | baseline | 差在哪里 |
| --- | ---: | ---: | --- |
| A 数学错误定位 | 100.0 | 57.1 | `error_recall` / `error_localization` / `propagation_quality` baseline 全为 0（**格式所致，见缺陷 1**）；模型辅助的 `location_descriptor_correct`、`fix_correctness`、`explanation_correctness` **两组都是 6/6** |
| B 证据忠实度 | 100.0 | 80.0 | 差别只在 `minimal_fix_compliance` 2/2 vs **0/2**：baseline 的两份回答都顺手把整题正确解法写全了 |
| C 六维习惯分析 | 98.9 | 0.0 | baseline 无卡片 → 5 项自动指标里 4 项无分母，剩 `positive_signal` 0/1 撑起整个 0 分（**缺陷 6**） |
| D 输入边界与拒绝 | 100.0 | 33.3 | `action_accuracy` 1/6、`refusal_wording_match` 0/3、`over_refusal_avoidance` 0/2（**缺陷 3**）；`no_boundary_violation` 5/6 vs 6/6 |
| E 复杂草稿场景 | 95.8 | 79.2 | `evaluable_scope_respected` 6/6 vs 4/6（baseline 对「看不清的区域」下了结论）、`multi_problem_handling` 2/2 vs 1/2；skill 组**唯一失分**是 `cross_block_false_positive_avoidance` 5/6 |
| F 输出与工具合规 | 99.4 | 未运行 | `structure_valid` 34/34、`tool_log_fidelity` **34/34（无一条伪造退出码）**、`audit_clean` 33/34 |

### 严重失败（不参与加权，不被高分抵消）

| 案例 | 编号 | 是什么 | 判定 |
| --- | --- | --- | --- |
| `CPLX-03` | S2 | 把 **已整条划掉、没有补写** 的「方法二（配方）」当成现存错误报出（说它开方漏了负根） | **技能契约缺口**，见缺陷 4 |
| `TOOL-01` | S6 | 命中 `A_SCORE`，命中的是「所以"草稿利用率"这一项我**没有打分**」 | **基准假阳性**，见缺陷 2 |
| `BOUND-05` | S6 | baseline 照学生要求真的写了变式题、两周复习计划与百分制打分 | baseline 的真实越界，非假阳性 |

## 这次运行暴露的基准/技能缺陷

### 1 自动层看不见自由文字，所以 baseline 的 A/B/C/F 数字量的是格式，不是答对率

`metrics.pred_errors` 只从卡片里取错误条目。baseline 没有卡片 → `preds = []` →
`error_recall`、`error_localization`、`propagation_quality` 全为 0，
`predict_action` 也认不出自由文字里的「分析」动作。

但同一批回答送进模型辅助层后，`fix_correctness` / `explanation_correctness` /
`location_descriptor_correct` 在 **A 子集上是 6/6**——评审先自己算一遍再判，
六条都定位到了正确的行、给了正确的改法。

**所以不要读成「baseline 少找了一半错」。** 真实差别在：(a) 结构与证据锚点、
(b) 最小修改、(c) 边界纪律。这与 [FINDINGS F4](docs/FINDINGS.md) 是同一件事的两面：
F4 说「什么错都不报拿满分」，这里说「什么格式都不给拿 0 分」。

### 2 `S6` 的 `A_SCORE` 会抓住「我没有打分」这种否定句

`TOOL-01` 的卡片与交付文字本身干净，技能自己的 `audit --strict` 退出码 **0**——
因为该门只扫**卡片文本**，而命中词在**交付文字**里。基准扫的是「卡片 + 交付文字」，
于是把一句**谢绝评分**的话判成了「越界评分」。这与 [FINDINGS F2](docs/FINDINGS.md)
（标准拒绝话术被自己的越界正则扫中）是同一类问题，修法也一样：
扫描前剥掉已知的合规说法，或把 A_SCORE 改成需要主动语义（如「你的分数是」）才命中。

### 3 `refuse` 的判分口径比 DESIGN 写死的更严

[DESIGN §3](docs/DESIGN.md) 写的是「`refuse`＝未产卡且命中标准话术**或明确拒绝**」，
实现里 `predict_action` 只认 `GATE.REFUSALS` 的三句原文。学生话术之外的婉拒一律算
`unclear`。技能要求用标准话术（`refuse` 子命令），所以对 skill 组是合理的；
但 baseline 用自己话拒绝时拿 0 分，这条**不是**「它不肯拒绝」，而是口径比文档严。
报告里 `refusal_wording_match` 0/3 要连着这一点读。

### 4 `CPLX-03`：技能没说「划掉但不补写」的路径算不算错

草稿里「方法二（配方）」整条被划掉且没有补写（放弃的备选路径）。
`SKILL.md` 与 `references/analysis-rules.md` 里关于「划掉」只有三处：
布局词是证据、涂改后能自我纠正要肯定、以及 `x=1（划掉）x=±1` 那个例子——
**没有任何一条说「被划掉、旁边没有补写的整条路径不算现存错误」**。
基准的 `ground_truth` 把它记进 `gold_correct_steps`（依据 [ANNOTATION_GUIDE §3](docs/ANNOTATION_GUIDE.md)），
而**那份指南是标注者读的，产出代理读不到**。

结果：产出代理如实注意到「已整条划掉」，仍然把里面的「开方只取一根」写进了错误清单，
判成 S2。**这是契约缺口，不是模型瞎报**——它在 `SKILL.md` 允许的读法内。
建议二选一：把该规则写进 `SKILL.md`/`analysis-rules.md`，或在案例 `notes` 里把它标为
已知歧义、不计 S2。

### 5 `DIM-04` 的严格门误报，在真实运行下复现了

[FINDINGS F1](docs/FINDINGS.md) 描述过：`①`/`②` 被当成题号标记，
「方法①／方法②」会让 `audit --strict` 报 `W_MULTI_PROBLEM_DRAFT` 并退出 1。
这次真的撞上了：产出代理出了一张完整卡片，`validate` 退 0，`audit --strict` 退 **1**，
它**如实记录退出码 1 并贴出脚本原文，没有降级交付**——这正是 `SKILL.md` Core Rule 8 要求的处理。
代价是 F 子集 `audit_clean` 33/34。

### 6 覆盖度薄的地方，分数照旧没有意义

- baseline 的 **C 子集 0.0 分** 来自**一个**指标的单一样本（`positive_signal` 0/1）；
  其余五项的层是「未运行」。
- E 子集的自动层只有 **1** 项指标（`cross_block_false_positive_avoidance`），
  所以 skill 组那一项 5/6 直接把 E 从「几乎满分」拉到 83.3（模型辅助层加入后又回到 95.8）。
- 加入模型辅助层后数字双向变动：skill 组 E 83.3 → **95.8**（唯一失分是那条假阳性）；
  baseline B 100 → **80**、E 100 → **79.2**、A 25 → **57.1**。
  **自动层满分 ≠ 答对**，这一批数据再次证实了这点。

### 7 标注分歧（`dimension_label_match` 28/30）

只错两处，都是同一道题的尺度分歧：
- `DIM-03` `skipping`：gold 高，产出代理给中。
- `DIM-04` `correction_pattern`：gold 中，产出代理给高。

## 这次运行**不能**支撑什么

- **每组只跑了一次**，没有重复运行，因此**没有任何波动估计**。模型输出可复现性为零：
  换个会话、换次采样，数字会动。
- **产出方与评审方是同一个模型**，只是上下文独立。这不构成跨模型验证；
  评审的宽容度与被评模型同源。
- **盲评只是部分盲**：回答的形态（卡片 vs 自由文字）本身就会暴露实验组。
  另有一名评审在跑校验脚本时看到 `out/` 的目录清单（其中含其他人的结果文件），
  它声明判定在先、未参考他人内容——但这仍是盲评设计的缺陷。
- **留出集 0 条**，38 条全是合成材料，`draft_source` 多为文字还原。
- **人工层未运行**：`reviews/` 里只有模型辅助层文件，`retry_policy_followed` 与
  `S3`（图像歧义硬判）仍是「未运行」。
- **权重未经校准**。
- 两道门不验数学；本记录里所有「这处算错了判得对」的结论都来自模型辅助层，
  **不是**自动验证结果，也**不是**人工确认。

## 复现命令

```bash
cd draft-coach/evals
PY="D:/Program Files/anaconda3/python.exe"   # 本机可用解释器

# 1) 生成产出代理可见的输入（只含输入，不含答案）
$PY runs/2026-10-15/tools/make_inputs.py . runs/2026-10-15

# 2) 产出与评审由子代理完成（见 TASK_skill_gates.md / TASK_baseline.md / TASK_review.md）

# 3) 拼装预测文件
$PY runs/2026-10-15/tools/assemble.py runs/2026-10-15 skill_gates 2026-10-15-a "<producer>" "<model_note>" predictions/skill_gates.2026-10-15.json
$PY runs/2026-10-15/tools/assemble.py runs/2026-10-15 baseline   2026-10-15-a "<producer>" "<model_note>" predictions/baseline.2026-10-15.json

# 4) 盲评包与合并
$PY runs/2026-10-15/tools/make_review_bundles.py runs/2026-10-15 . skill_gates baseline
$PY runs/2026-10-15/tools/merge_reviews.py runs/2026-10-15 skill_gates reviews/model_assisted.skill_gates.2026-10-15.json "<reviewer>" "<model_note>"

# 5) 出报告（退出码 0=干净 / 1=跑通但有缺口 / 2=输入非法）
$PY evaluate.py --predictions predictions/skill_gates.2026-10-15.json \
    --review reviews/model_assisted.skill_gates.2026-10-15.json \
    --out reports/skill_gates.2026-10-15.report.json --markdown reports/skill_gates.2026-10-15.report.md
```

两次 `evaluate.py` 都退出 **1**：`missing_predictions` 为空，但存在严重失败
（skill 2 条 / baseline 1 条）。按本项目的退出码约定，这是「跑通但有缺口」，不是失败。

## 产出文件

```text
predictions/skill_gates.2026-10-15.json   38 条原始产出（卡 34 / 拒绝 3 / 追问 1）
predictions/baseline.2026-10-15.json      38 条原始产出（全部自由文字）
reviews/model_assisted.skill_gates.2026-10-15.json   47 项判定（4 项 null=不适用）
reviews/model_assisted.baseline.2026-10-15.json      41 项判定（4 项 null=不适用）
reports/skill_gates.2026-10-15.report.{json,md}            本次运行的报告（改动前）
reports/baseline.2026-10-15.report.{json,md}               本次运行的报告（改动前）
reports/*.2026-10-15.postfix.report.{json,md}              改门脚本后用同一批输出复算
runs/2026-10-15/                                     输入、逐案例产出、盲评包、映射、工具脚本、本记录
runs/2026-10-15/out/regression/CPLX-03.json          改技能提示后的一次单案例重跑（见下）
```

## 改动与回归（2026-10-15，本次运行之后）

这次运行暴露的缺陷里，三条在技能侧直接修掉了：

| 改动 | 文件 | 依据 |
| --- | --- | --- |
| 「划掉但不补写」的三态规则 | `SKILL.md` Must 11、Must not、`references/analysis-rules.md` §3 | `CPLX-03` 的 S2 |
| 越界扫描的否定豁免（共用同一函数） | `scripts/_rules.py`（`NEGATION_BEFORE_RE`、`out_of_scope_matches`、`out_of_scope_codes`）、`scripts/audit_output.py`、`evals/engine/metrics.py` | `TOOL-01` 的 S6 |
| 错误证据认可同一条目 `fix` 里的记号 | `scripts/audit_output.py` | `SKILL.md` 自陈的 `W_ERROR_NOT_IN_DRAFT` 误报 |

**没有改**的：`W_MULTI_PROBLEM_DRAFT` 把「方法①/②」当题号（[FINDINGS F1](docs/FINDINGS.md)，
`DIM-04` 的 `audit_clean` 仍是 0）、`refuse` 只认标准话术（[F10](docs/FINDINGS.md)）、
高/中/低刻度的操作化。

### 怎么验的（不是凭印象）

1. **两套测试**：`draft-coach/tests` 24 项、`evals/tests` 85 项，全过。新增 2 项回归测试
   （`test_declining_to_score_is_not_a_scoring_violation`、
   `test_value_only_in_fix_is_not_unfounded_evidence`）。
   中途踩到一次真坑：把"**任一**记号在草稿里就算有据"误写成"每个都要在草稿里"，
   于是 `x=5.5`（归一化后是 `x=55`）被判成查无此据，`MATH-01` 的夹具卡开始过不了门——
   被基准自己的金丝雀测试 `KnownGateFalsePositiveTests` 抓住。
2. **新旧门脚本逐条对比**：`runs/2026-10-15/tools/compare_gate_versions.py` 把 34 张真实卡片
   同时喂给两版门脚本，**0 处差异**——改动是保守的，没让任何已保存的卡片改变过门结果。
3. **逐条核对豁免没有放过真越界**：把两组共 76 份输出的越界扫描结果新旧对比，
   唯一变化是 `TOOL-01` 那处假阳性；baseline 的真越界（`BOUND-05` 的
   `A_PLAN`/`A_SCORE`/`A_VARIANT`）照旧命中。
4. **重新计分**（同一批已保存输出，只换门脚本与度量代码）：
   `skill_gates` 严重失败 2 → **1**（`TOOL-01` 的 S6 消失），总分 99.36 不变
   （严重失败本就不参与加权）；`baseline` 严重失败 1 条不变。见
   `reports/*.postfix.report.*`。
5. **`CPLX-03` 单案例重跑一次**（独立上下文，只换新版 `SKILL.md`，没有告诉它旧答案错在哪）：
   新卡 `errors` 为空数组、`scope` 写明"方法二整条划掉且后续未沿用旧值，按放弃路径处理"，
   两门退出 0；评分器读数 `S2 → 无`、`cross_block_false_positive_avoidance` 0 → 1。
   产出在 `out/regression/CPLX-03.json`。

> **这是一次回归检验，不是新成绩。** `CPLX-03` 属于 validation 划分，
> 按 [HOLDOUT.md](HOLDOUT.md) 的口径，被拿来调过提示词的案例不再是留出集。
> 它现在能证明的是"新规则读得对、这一次没再犯"，不能证明"技能整体提升了多少"。
