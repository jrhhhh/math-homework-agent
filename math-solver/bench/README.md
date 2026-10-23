# Math Solver 基准

对**已保存的** math-solver 输出做确定性评分，**不调用任何模型 API**。

它评四件事：

1. **答案是否正确**（含多解、空集、区间、分段答案）。
2. **核验是否诚实**（定义域、增根、端点、分支、判别式等检查是否真的出现）。
3. **状态与答案形态是否正确**（`solved`、`needs_clarification`、多值答案、假命题）。
4. **边界是否守住**（学生已有解答、草稿、优化请求、只有图片时，不乱做题）。

## 当前状态

| 项目 | 状态 |
| --- | --- |
| 案例 | **51 条**：answer_core 26 / verification_discipline 16 / status_handling 5 / boundary_routing 4 |
| 数据划分 | development 46 / test 5（MATH-08、12、14、21、29） |
| 自动层 | 已实现：结构门、答案检查、核验点、分支、禁词、tool_log、严重失败 |
| 基准测试 | **29 项通过**（`tests/`） |
| 夹具读数 | oracle **100**、0 严重失败、退出 0；bad **76.11**、12 类严重失败、退出 1 |
| 人工层 | 接口已实现（`engine/human_review.py`），尚未运行 |
| 模型运行 | **没有**。`predictions/fixtures/` 是夹具，不是模型成绩 |
| 数学真值 | 25 道扩充题来自独立核验的输出；另 3 道新增求解题（概率、向量、证明）、4 条边界案例与 2024 新高考Ⅰ卷 19 题 |

## 真值来源

25 道扩充题的答案来自**独立核验**（SymPy / 代回 / 分支检查），不是用户提供的参考答案。
那份参考答案有 6 处需要修正（1.3、1.4、1.5、2.5、3.3、4.2），逐项证据见
[`../example/mvp-2026-10-18-expanded/reference_check.md`](../example/mvp-2026-10-18-expanded/reference_check.md)。

另 3 道求解题（概率、向量、证明）与 4 条边界案例是本基准新增的，答案在
`fixtures/solutions/` 与 `tools/data.py` 中给出。

**2024 新高考Ⅰ卷 19 题**（MATH-33–MATH-51）单独收录在
[`tools/exam_2024.py`](tools/exam_2024.py)，solution 夹具在
`fixtures/solutions/2024_xgk1/`。题面采用通行真题版本，修正了原始转录中的错误：
第 16(2) 按“△ABP 面积为 9”收两条直线，第 17–19 题按标准题面。所有 19 条均为
`development`，不算独立 test 留出集。

## 快速开始

在 `math-solver/bench/` 下：

```bash
# 1) 校验案例与标准答案
python3 schema_check.py

# 2) 跑基准自身测试
python3 -m unittest discover -s tests -p 'test_*.py'

# 3) 生成 oracle 夹具并评分（应 total=100，退出 0）
python3 make_fixture_predictions.py --mode oracle --out predictions/fixtures/oracle.json
python3 evaluate.py --predictions predictions/fixtures/oracle.json \
    --out reports/fixtures/oracle.report.json \
    --markdown reports/fixtures/oracle.report.md

# 4) 故意破坏的夹具（应退出 1，并列出严重失败）
python3 make_fixture_predictions.py --mode bad --out predictions/fixtures/bad.json
python3 evaluate.py --predictions predictions/fixtures/bad.json --strict
```

Windows 上 `python3` 可能是应用商店占位程序；本机用
`"D:/Program Files/anaconda3/python.exe"`。测试内部一律用 `sys.executable`。

退出码：**0** 达标 · **1** 低于 `--fail-under`，或 `--strict` 下有严重失败 · **2** 输入非法。
`schema_check.py` 用 **0/1/2**（通过 / 数据不合格 / 输入非法）。

## 四个子集

| 子集 | 案例 | 权重 | 评什么 |
| --- | ---: | ---: | --- |
| `answer_core` | 26 | 45 | 方程、函数、数列、三角、几何、向量、概率、证明的最终答案 |
| `verification_discipline` | 16 | 30 | 定义域、增根、端点、参数分类、分支完备、无解 |
| `status_handling` | 5 | 15 | 多值答案、分段答案、假命题、多解三角方程 |
| `boundary_routing` | 4 | 10 | 学生解答 / 草稿 / 优化请求 / 只有图片时的转交与澄清 |

## 预测文件

```json
{
  "arm": "skill_gates",
  "model": "your-model",
  "run_id": "2026-10-18-run-1",
  "predictions": [
    {
      "case_id": "MATH-01",
      "action": "solve",
      "output": { "...六字段 solution JSON..." },
      "tool_log": [
        {"command": "python3 scripts/validate_output.py validate --card x.json --strict",
         "exit_code": 0}
      ]
    },
    {
      "case_id": "MATH-29",
      "action": "route",
      "route_to": "math-error-diagnosis",
      "reply": "这是检查已有解答的任务，应转交 math-error-diagnosis。"
    },
    {
      "case_id": "MATH-32",
      "action": "clarify",
      "reply": "请把图片里的题面打成文字或口述给我；我不直接读取图片上的字符。"
    }
  ]
}
```

- `action` 是 `solve` / `route` / `clarify`。
- `skill_gates` 组的 solve 案例必须记录 `validate_output.py validate --strict`；
  评测器会重放结构门，声称退出码与实测不一致记 `S_TOOL_LOG_MISMATCH`。
- `route` / `clarify` 不要求 tool_log，但不得附带 solution JSON。
- 标准答案与案例分文件：`cases.jsonl` 只含输入与预期动作，
  `ground_truth.jsonl` 只含答案检查、核验点、禁词与理由。

## 评分怎么算

1. **案例分** = 该案例适用检查的加权平均（0–1）。
2. **严重失败**直接把该案例记 0，不被其他检查抵消，并在报告里单独列出。
3. **子集分** = 该子集案例分均值 × 100。
4. **总分** = 子集分按上表权重加权。
5. 另列 **答案正确率**、**状态正确率**、**核验诚实率**、**边界路由分** 与 **数据划分分**；
   答案/状态正确率附 **95% Wilson 区间**。51 条样本下区间仍然很宽，不要把点估计当作稳定准确率。

读分时必须同时看：总分、答案正确率、严重失败列表、覆盖度。
一个总分不低但带若干严重失败的运行，不是可交付的运行。

### 严重失败代码

`S_MISSING_PREDICTION` · `S_MISSING_OUTPUT` · `S_WRONG_ACTION` ·
`S_STRUCTURE_GATE` · `S_WRONG_STATUS` · `S_FALSE_VERIFICATION` ·
`S_CONFIDENCE_CLAIM` · `S_FALSE_TOOL_CLAIM` · `S_WRONG_ROUTE` ·
`S_OCR_CLAIM` · `S_MISSING_TOOL_LOG` · `S_TOOL_LOG_MISMATCH`

注意：**答案错误不是严重失败**。它由 `answer_correct` 扣分，并单独计入答案正确率；
严重失败留给契约、边界与诚实性问题。

## 答案检查类型

| 类型 | 用于 | 做法 | 限制 |
| --- | --- | --- | --- |
| `value_set` | 数值根、参数值集合 | 抽取答案中的数值（支持分数与 `±`）做集合比较 | 答案里混入标签数字时可能误读；复杂答案改用其他类型 |
| `interval_set` | 定义域、解集 | 解析 `[a,b)`、`∪`、`∞` 并比较开闭端点 | 不支持带参数 `kπ` 的区间族 |
| `text_forms` | √、π、多值和、文字结论 | 每组关键词至少命中一个 | 关键词匹配，不做语义等价 |
| `piecewise` | 参数分段答案 | 要求“分支标签 + 对应结论”出现在同一句段 | 依赖分号/句号切分，措辞变化可能误判 |
| `empty_set` | 无解 / 空集 | 检测“无解 / 空集 / ∅” | 可能被否定句误触发 |

这些检查面向本基准的固定案例，**不是通用数学等价判定器**。推导是否优雅、
方法是否最优、教学备注是否真的有用，自动层不判断，只走人工层。

## oracle / bad 夹具

- `--mode oracle`：用已保存的 25 份扩充输出 + 3 份新增求解输出拼成预测。
  **oracle 得 100 分只说明评分流程自洽，不是模型质量证据。**
- `--mode bad`：在 oracle 上定点破坏——错误答案、状态冲突、缺 tool_log、
  伪造退出码、错误转交、OCR 声明、占位式核验、置信度措辞、伪工具声明、
  缺输出、错误动作、缺预测。当前夹具覆盖全部 **12 类严重失败**；
  端到端测试断言它能被抓住并退出 1。

## 人工层

自动层回答不了“推导是否真的严谨、方法是否适合高中生、教学备注是否有用”。
导出模板：

```bash
python3 engine/human_review.py export \
    --predictions predictions/fixtures/oracle.json \
    --out reviews/human.template.json
python3 engine/human_review.py merge --reviews reviews/human.template.json
```

模板里四项均填 1–5 分；人工分**单独统计，不并入自动分**。
当前尚未运行人工评审，也没有人工评分数据。

## 这套评测做不到什么

- **结构门不验数学**；答案检查只覆盖固定案例的答案形态，不能替代一般性证明。
- **核验点检查是关键词匹配**：可能出现“写了关键词但没真的做检查”的情况，也可能误判同义表述。
- **分支检查依赖句子切分**：同一句里堆多个分支时，标签与结论的对应可能被放宽。
- **51 条是合成/整理出来的案例**，不是随机抽样；不能外推为任意高考题的准确率。2024 新高考Ⅰ卷 19 题虽是真题，但标准答案仍是人工整理，自动分不验证推导严谨性。
- **test 划分不是独立留出集**：MATH-08、12、14、21、29 也参与过技能与数据开发，
  只能当作报告分层，不能当作泛化估计。
- **没有模型运行数据**；`predictions/fixtures/` 是夹具。
- **没有人工标注一致性数据**；人工层接口已实现但未运行。
- **权重未经试运行校准**；子集覆盖薄时高分不能外推。

## 目录

```text
cases.jsonl / ground_truth.jsonl   案例与标准答案（交付物）
config.json                        权重、严重失败代码、tool_log 要求
evaluate.py                        评分入口
schema_check.py                    数据自洽与防泄漏检查
make_fixture_predictions.py        oracle / bad 夹具
engine/data.py                     数据加载
engine/answers.py                  答案检查器
engine/gates.py                    结构门重放与 tool_log 核对
engine/checks.py                   逐案例检查与严重失败
engine/scoring.py                  聚合、子集/划分分
engine/report.py                   Markdown 报告
engine/human_review.py             人工层导出 / 回读
tools/data.py                      案例与标准答案源
tools/exam_2024.py                 2024 新高考Ⅰ卷 19 条案例与真值
tools/build_dataset.py             重建 JSONL
fixtures/solutions/                概率、向量、证明三份新增求解输出
fixtures/solutions/2024_xgk1/      2024 新高考Ⅰ卷 19 份 solution 夹具
tests/                             29 项单元与端到端测试
predictions/fixtures/              夹具（不是模型输出）
reports/fixtures/                  夹具报告
```

## 改案例

改 `tools/data.py`；2024 新高考Ⅰ卷的 19 条案例改 `tools/exam_2024.py`，并同步更新
`fixtures/solutions/2024_xgk1/` 下对应的 solution JSON。然后：

```bash
python3 tools/build_dataset.py
python3 schema_check.py
python3 -m unittest discover -s tests -p 'test_*.py'
python3 make_fixture_predictions.py --mode oracle --out predictions/fixtures/oracle.json
python3 evaluate.py --predictions predictions/fixtures/oracle.json \
    --out reports/fixtures/oracle.report.json --markdown reports/fixtures/oracle.report.md
python3 make_fixture_predictions.py --mode bad --out predictions/fixtures/bad.json
python3 evaluate.py --predictions predictions/fixtures/bad.json --strict   # 应退出 1
```

**改完必须重跑真实输出**，不能凭印象写「应该会通过」。
