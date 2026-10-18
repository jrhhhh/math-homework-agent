# 设计说明

本文解释 `math-solver/bench/` 为什么这样评分、每个检查在问什么、哪些事它不做。
行为依据只有一份：[`../SKILL.md`](../SKILL.md)。

## 1. 评的是「求解 + 核验 + 边界」，不是单点答案

math-solver 的职责不是只给一个数，而是：解析题目、选高中方法、分步推导、
独立核验、按契约输出状态与教学备注。因此基准分成四个子集：

| 子集 | 问什么 |
| --- | --- |
| `answer_core` | 最终答案对不对，覆盖代数、函数、数列、三角、几何、向量、概率、证明 |
| `verification_discipline` | 定义域、增根、端点、参数分类、分支完备、无解是否被检查 |
| `status_handling` | 多值、分段、假命题、多解三角方程是否完整表达 |
| `boundary_routing` | 学生已有解答、草稿、优化请求、只有图片时是否转交/澄清 |

权重 45/30/15/10 是**工程判断**，不是统计校准结果。答案仍然是最大权重，
但核验与边界占了 40%，避免「答案蒙对就算过」。

## 2. 案例与标准答案分离

`cases.jsonl` 只含：

- `case_id`、`subset`、`split`、`grade_level`
- `input`：题目、学生解答、草稿、指定方法
- `expected_action`：`solve` / `route` / `clarify`
- `expected_status`、`expected_route`
- `tags`

`ground_truth.jsonl` 只含：

- `answer_check`：答案检查规格
- `required_checks`：核验节必须出现的关键词组
- `required_terms`：答案/条件/推导必须出现的结论项
- `forbidden_terms`：案例特定的错误说法
- `must_include`：转交/澄清回复必须覆盖的说明
- `rationale`：为什么这是标准答案

分开存放便于「造输入」与「写标准答案」独立工作，也避免案例文件泄漏答案。

## 3. 答案检查不是通用 CAS

自动层用五类固定检查：

1. **`value_set`**：抽取数值集合。支持 `x=±3`、分数、集合写法。
2. **`interval_set`**：解析区间并比较开闭端点，支持 `∪` 与 `∞`。
3. **`text_forms`**：每个关键词组至少命中一个，用于 `√7`、`π/3`、
   两个 S₅、两个角、反例结论等。
4. **`piecewise`**：按参数分支检查「标签 + 对应结论」是否出现在同一句段。
5. **`empty_set`**：检测无解/空集。

为什么不做通用符号等价？因为把中文答案字符串稳定解析成 SymPy 表达式，
本身就是一个容易误判的工程问题；对固定案例，显式规格更可控、可审查。
代价是：**新增案例需要写清楚答案规格**，且 `text_forms`/`piecewise` 仍是关键词匹配，
换一种等价措辞可能被判错。这个代价写在 README 的能力边界里。

## 4. 核验纪律

`required_checks` 要求 `verification.checks` 的 name/details 中出现对应概念，
例如：

- 根式/分式方程：`定义域`、`增根`、`舍去`。
- 二次不等式/参数题：`分类`、`端点`、`判别式`、`根`。
- 数列：`q=-2`、`公比`、`求和`。
- 三角：`象限`、`参考角`、`区间`。

它检查的是「核验节有没有写这件事」，**不检查这条核验本身做得对不对**。
关键词可以被堆砌，也可以因同义表述而漏判；这是自动层的已知限制。
人工层才判断推导是否真的成立、方法是否适合高中生。

## 5. 状态处理

- `solved` 案例要求 `output.status == "solved"`，且结构门通过。
- 无解题（MATH-23）仍可 `solved`：题目被完整解决，答案是空集。
- 假命题（MATH-27）仍可 `solved`：判断与反例已给出。
- 多值题（MATH-24、26、28）要求把所有分支写全；漏一个分支会扣
  `answer_correct` 与 `required_terms`。
- 参数分段题（MATH-17、20、21、22、25）用 `piecewise` 检查标签与结论的对应。

这里没有 `needs_clarification` 的正面案例；它作为边界出口由 MATH-32 的
`clarify` 覆盖。MATH-31 也用 `clarify`，但内容是「当前无优化技能」的边界说明，
不是题目条件不足。如果将来加入「题目条件不足」案例，应新增
`expected_status: needs_clarification` 的 solve 分支。

## 6. 边界路由

- MATH-29：学生已有正式解答且要求检查 → `route_to: math-error-diagnosis`。
- MATH-30：草稿版面 → `route_to: draft-coach`。
- MATH-31：已成立解法要求优化 → `clarify`：说明当前项目不提供优化技能，不重做解答、不冒充优化。
- MATH-32：只有图片 → `clarify`，要求文字/转写，**不得声称读出图片字符**。

路由检查看 `route_to`、回复是否覆盖必要说明、是否附带 solution JSON、
是否出现 OCR 声明。它**不判断**转交后的技能是否真的完成了工作。

## 7. 严重失败与质量分分开

严重失败直接把案例记 0，不参与加权抵消：

- `S_MISSING_PREDICTION` / `S_MISSING_OUTPUT`
- `S_WRONG_ACTION` / `S_WRONG_STATUS` / `S_WRONG_ROUTE`
- `S_STRUCTURE_GATE`
- `S_FALSE_VERIFICATION`
- `S_CONFIDENCE_CLAIM` / `S_FALSE_TOOL_CLAIM`
- `S_OCR_CLAIM`
- `S_MISSING_TOOL_LOG` / `S_TOOL_LOG_MISMATCH`

**答案错误不是严重失败**。它由 `answer_correct` 扣分，并单独计入答案正确率。
这是有意的：答案错是质量问题，需要一个可解释的分数；越界、伪造、错误路由是
契约问题，不能靠其他检查抵消。

## 8. 结构门与 tool_log

`engine/gates.py` 用 `sys.executable` 重放
`../scripts/validate_output.py validate --card ... --strict`。

- `skill_gates` 组必须记录 validate 命令；缺记录记 `S_MISSING_TOOL_LOG`。
- 声称的退出码与实测不一致，或命令缺少 `--strict`，记 `S_TOOL_LOG_MISMATCH`。
- 结构门只查 JSON 形状与状态一致性，**不验数学**。

这只能发现「记录了假退出码」，不能发现「模型根本没读题」。

## 9. 数据划分

32 条案例中：

- `development` 27 条；
- `test` 5 条：MATH-08、MATH-12、MATH-14、MATH-21、MATH-29。

`evaluate.py` 会在报告里单独列出两个划分的得分。test 只有 5 条，而且这些案例
也参与过技能与数据开发，**不是独立留出集**；只能做冒烟检查，不能外推为稳定泛化估计。

## 10. oracle / bad 夹具

- oracle 用已保存的 25 份扩充输出 + 3 份新增求解输出 + 4 条边界回复拼成。
  它得 100 分只说明评分流程自洽，**不是模型质量证据**。
- bad 在 oracle 上定点破坏：错误答案、状态冲突、缺 tool_log、伪造退出码、
  错误转交、OCR 声明、占位式核验、置信度措辞、伪工具声明、缺输出、错误动作、缺预测。
  端到端测试断言这些都能被抓住；当前夹具触发全部 12 类严重失败，总分 60.5。
- bad 夹具的总分仍可能不低，因为大多数案例是完好的；读分时必须看
  `severe_count` 与逐案例表，不能只看总分。

## 11. 人工层

自动层回答不了：

1. 推导是否真的严谨、有没有跳步或循环论证？
2. 方法是否适合高中生，是否用了超纲工具？
3. `teaching_notes` 是否真的对这道题有用？

`engine/human_review.py` 只提供导出/回读接口，人工分单独统计，不并入自动分。
当前尚未运行，也没有人工标注一致性数据。

## 12. 不做的事

- 不调用模型，不做自动重试。
- 不做通用数学等价判定；答案检查只覆盖固定案例。
- 不验证推导的每一步是否数学成立；核验点是关键词检查。
- 不判断方法是否最优，不判断教学备注质量（留给人工层）。
- 不做 OCR，不把图片内容当证据。
- 不声称这 32 条能代表任意高中题或高考题。
