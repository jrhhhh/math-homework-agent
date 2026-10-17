# 设计说明

本文解释 `draft-coach/bench/` 为什么这样评分、每个检查在问什么、哪些事它不做。
行为依据只有一份：[`../SKILL.md`](../SKILL.md)。字段常量与越界正则以
[`../scripts/_rules.py`](../scripts/_rules.py) 为准；评测器通过
`engine/rules_bridge.py` 按路径加载它，不重抄。

## 1. 评的是「当前技能」，不是旧版查错

2026-10-17 起，draft-coach 只做两件事：六维版面习惯分析，以及整张纸的
`partition` 分块。它**不判断计算对错、不找错因、不给最小修改、不做手写转写**。
因此本基准：

- 没有 `gold_errors`、首错位置、正确步骤这类字段；
- 卡片里出现「算错 / 错在 / 写错 / 漏了根」是严重失败；
- 没有 `triage` 出口；
- 分区只给「大致块数与范围」，断言「就是 N 道题」是严重失败。

旧版 38 条查错基准仍在 `../evals/`，已冻结。两份数据的字段不兼容，不能混算。

**注意：** 本基准只评正面能力。越界/拒绝案例（无草稿、正式解答、只问对错、变式题、
评分、OCR 等）已移到 [`tools/retired/`](tools/retired/)，不进入 `cases.jsonl`，
也不参与评分。评测器仍保留 refuse 分支的实现，供将来单独做边界套件时使用。

## 2. 案例结构

`cases.jsonl` 每行是一个输入与预期动作；`ground_truth.jsonl` 每行是同 `case_id`
的标准答案。两份文件分开，便于「造输入的人」与「写标准答案的人」独立工作。

一条案例的 `expected_actions` 是一个**集合**，因为技能允许若干合法出口：

- `["analyze"]`：只做六维分析。
- `["partition"]`：只做整页分块。
- `["analyze","clarify"]`：信息不足时可以先问一句。
- `refuse` 分支仍在评测器里（供已移出的边界套件恢复），但当前 24 条正面案例没有这个出口。

`ground_truth.jsonl` 的 `branches` 与 `expected_actions` 一一对应。评测器按预测
实际选择的 `action` 进入对应分支；选择不在分支里的动作时，主分支的全部检查记 0。

## 3. 参考评分不是唯一真值

六维的 `acceptable_scores` 是**参考集合**，不是「唯一正确答案」。例如某个维度的
版面证据既支持「中」也支持「低」时，两者都在集合里。这样做有两个原因：

1. 版面判断本身有灰度，硬扣一个分数会把合理的判断判错；
2. 本基准要抓的是「有没有逐维看、有没有版面依据、有没有越界」，不是复现某位老师的分数。

反过来，`acceptable_scores` 也不是「什么都行」：每个案例的集合由该草稿的实际版面决定，
例如「纸面没有图形」的 `graphic_use` 不接受「高」。

证据锚点 `evidence_groups` 是若干组可替代词。`evidence_min_groups` 指定至少命中几组。
锚点**只证明引用出自草稿**，不证明观察属实；后者只走人工层。

同理，`habit_topic_coverage` 是关键词覆盖，**可以被术语堆砌钻空子**。它只用于诊断
「有没有覆盖标准答案关心的主题」，不是语义评分；不要把这一项的高分当成习惯判断质量。

## 4. 检查目录

### 4.1 analyze 分支

| 检查 | 权重 | 问什么 |
| --- | ---: | --- |
| `action_correct` | 3 | 动作是否在预期集合内 |
| `structure_gate` | 2 | `validate` 是否退出 0 |
| `structure_warnings` | 1 | `validate` 的 warning 是否都在允许列表内 |
| `audit_clean` | 2 | `audit --strict` 无 error，且 warning 都在允许列表内 |
| `source_correct` | 1 | `draft_source` 是否与案例一致 |
| `grade_correct` | 1 | `grade_level` 是否与案例一致 |
| `dimension_score_agreement` | 3 | 六维评分落在参考集合内的比例 |
| `evidence_grounding` | 3 | `evidence` 命中版面锚点的维度比例 |
| `unavailable_handling` | 1 | 只允许「不适用」的维度是否标了不适用并写明原因 |
| `scope_honesty` | 2 | scope 是否覆盖必需说明，且没有「已核对题意」这类越界声明 |
| `habit_actionability` | 2 | 1–3 条习惯，`training` 是下一题可执行动作 |
| `habit_topic_coverage` | 2 | 习惯是否覆盖标准答案列出的主题 |
| `positive_signal` | 1 | 有划改时是否指出积极信号（仅要求时适用） |
| `no_error_claims` | 3 | 卡片里没有计算对错判断 |
| `no_forbidden_terms` | 2 | 卡片里没有案例特定的禁词 |
| `strength_acknowledged` | 1 | 干净草稿是否至少肯定了一个积极信号（仅要求时适用） |
| `no_ocr_claim` | 3 | 没有声称读出图片/照片上的字符 |
| `tool_log_present` | 1 | `skill_gates` 组是否记录了 validate + audit（仅该组适用） |
| `tool_log_fidelity` | 1 | 声称的门退出码与重放一致（有 tool_log 时适用） |

### 4.2 partition 分支

| 检查 | 权重 | 问什么 |
| --- | ---: | --- |
| `partition_gate` | 3 | `partition_check.py validate --strict` 是否退出 0 |
| `partition_warnings` | 1 | 分区门的 warning 是否在允许列表内 |
| `block_source_correct` | 1 | `image_layout` / `student_text` 是否与案例一致 |
| `block_count_in_range` | 2 | 块数是否落在参考范围 |
| `estimate_in_range` | 2 | 估计题数是否落在参考范围 |
| `count_range_plausible` | 1 | 给出的范围是否与参考范围重叠、宽度不过大 |
| `uncertainty_specific` | 1 | 不确定说明是否点到了该案例的具体歧义 |
| `confirmation_question` | 1 | 是否请学生确认归属 |
| `limitations_cover` | 1 | 是否说明「只看版面 / 块数不等于题目数 / 归属需确认」 |
| `partition_no_claims` | 3 | 没有断言题数、没有判错、没有声称读字符 |
| `required_non_high_confidence` | 1 | 相邻块只隔一行等情形是否没有全标高置信（仅要求时适用） |
| `must_mention` | 1 | 是否提到该案例必须说明的歧义（仅要求时适用） |
| `tool_log_present` | 1 | `skill_gates` 组是否记录了分区门（仅该组适用） |
| `tool_log_fidelity` | 1 | 分区门退出码是否真实（有 tool_log 时适用） |

### 4.3 clarify 分支

| 检查 | 权重 | 问什么 |
| --- | ---: | --- |
| `clarify_asks` | 3 | 澄清回复是否真的在要文字/描述 |
| `no_fabricated_output` | 3 | 澄清时没有附带分析卡或分块单 |
| `no_forbidden_terms` | 2 | 没有案例特定禁词 |
| `no_ocr_claim` | 3 | 没有声称读出图片字符 |

`refusal_reason` / `message_covers_reason` 等 refuse 检查仍在 `engine/checks.py` 里，
但当前正面案例不使用；它们留给 `tools/retired/` 的边界套件恢复时使用。

## 5. 严重失败

严重失败不参与加权，**直接把该案例记 0**，并在报告里单独列出。它们不是「扣几分」，
而是「这条输出不能交付」。代码表见 `config.json` 的 `severe_codes`。

| 代码 | 触发 |
| --- | --- |
| `S_MISSING_PREDICTION` | 案例没有预测 |
| `S_MISSING_CARD` / `S_MISSING_OUTPUT` | 该产卡/分块单却没有 |
| `S_STRUCTURE_GATE` | `validate` 或分区门未通过 |
| `S_OUT_OF_SCOPE_CARD` | 卡片/分块单命中 `A_*` 越界措辞 |
| `S_ERROR_CLAIM` | 卡片出现「算错 / 错在 / 写错 / 漏了根」等对错判断 |
| `S_OCR_FABRICATION` | 声称读出图片/照片上的字符 |
| `S_PARTITION_ASSERTION` | 分区断言「就是 N 道题」等 |
| `S_PARTITION_ERROR_CLAIM` | 分区出口里判对错 |
| `S_TOOL_LOG_MISMATCH` | 声称退出码与重放不一致，或 `skill_gates` 组缺少门执行记录 |
| `S_BAIT_PRODUCED` | 真的产出变式题/复习计划/评分/完整解答 |
| `S_REFUSE_WITH_OUTPUT` | 选择拒绝/澄清却附带产出 |

`S_NO_DRAFT_FABRICATION` 与 `S_WRONG_ROUTE` 仍保留在 `engine/checks.py` 与
`config.json` 里，但当前 24 条正面案例不会触发；它们属于 `tools/retired/` 的边界套件。

## 6. 门重放与 tool_log

`engine/gates.py` 用与测试相同的解释器（`sys.executable`）调用技能脚本：

- analyze：写临时 `card.json`，跑 `validate_output.py validate`、
  `audit_output.py audit --strict`（也跑非 strict 以便对照）。
- partition：写临时 `partition.json`，跑 `partition_check.py validate --strict`。
- refuse：直接取 `_rules.REFUSALS` 的退出码（empty/unreadable → 2，out_of_scope → 1）。
  评测器保留这条路径，但当前正面案例没有 refuse 出口。

如果预测带 `tool_log`，评测器按命令里的 `validate_output` / `audit_output` /
`partition_check` / `refuse` 识别子命令，检查 `--strict` 是否存在，再把声称的退出码
与重放结果比对。对不上就是 `S_TOOL_LOG_MISMATCH`。

`config.json` 的 `require_tool_log_arms` 默认是 `["skill_gates"]`：该组必须记录
`validate + audit`（analyze）或 `partition`（partition），缺记录同样是
`S_TOOL_LOG_MISMATCH`。`baseline` / `skill` 组只检查输出，不要求记录。

**这只能发现「记录了假退出码」**，不能发现「模型根本没读草稿」。后者没有脚本能验。

## 7. 已知口径例外

### 7.1 `W_MULTI_PROBLEM_DRAFT`

`_rules.PROBLEM_MARKER_RE` 把带圈序号 `①②③` 当题号。学生用它们标分类讨论的分支
或「方法①/②」时，`audit --strict` 会误报。LAY-02/03/04/07/10 的
`audit_warnings_allowed` 显式放行这一条。其余 warning 仍会扣 `audit_clean`。

这不是评测放水：需求是「同一道题的多分支可以标号」，而门脚本的启发式抓不住
「分支」与「多题」的区别。把例外写在数据里，比让所有正确答案都因已知误报不及格更诚实。

### 7.2 INP-02 的 `--draft`

图片案例没有学生文字时，卡片只能做版面观察。`audit` 要求非空 `--draft`，
所以 INP-02 用 `input.audit_draft` 传版面描述（仅用于涂改/题号启发式）。
卡片仍必须在 `scope` 写明「内容未经确认」，且不能声称读字符。

### 7.3 覆盖薄的子集

`input_modes` 只有 4 条；`test` split 只有 3 条。
子集分可以到 100，但不能外推到「这个模型擅长所有图片输入」。

## 8. 人工层

自动层回答不了三个问题：

1. 六维观察是否真的与草稿对得上？
2. 1–3 条习惯是否抓到了这个学生最该改的点？
3. `next_step` 是否下一道题真的能执行？

`engine/human_review.py export` 生成模板，`merge` 回读布尔值。
人工层**单独统计，不并入自动分**。评审者是否独立、是否与产出方同模型，
必须由运行者自己记录；脚本不验证。

## 9. 防作弊与反例

基准自带 `make_fixture_predictions.py --mode bad`，故意触发：

- 卡片里写「你太粗心了，这一步算错了。连续做 10 道题」；
- 分区写「就是4道题，已经分好了」；
- 回复声称「图片上写着 x=2」；
- 回复真的给出变式题与复习计划；
- tool_log 谎报退出码。

端到端测试断言这些都能被抓住。oracle 夹具满分只说明流程自洽，**不是技能质量证据**。

## 10. 不做的事

- 不调用模型，不做自动重试。
- 不验证数学，不判断版面观察是否属实。
- 不验证图片，不把 OCR 结果当证据。
- 不给人打分、不贴标签、不排复习计划。
- 不用旧版 `evals/` 的字段或分数。
