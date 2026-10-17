# Draft Coach 版面习惯基准

面向**当前** draft-coach（2026-10-17 起：只看版面、不判对错、不做手写转写）的独立基准。
旧版「查错」基准在 [`../evals/`](../evals/)，已冻结，不要用它给当前技能打分。

**本基准只评正面能力**：六维版面分析、证据纪律、整页分区、输入形态。
越界/拒绝类案例（无草稿、只问对错、变式题、评分、OCR 等）**不在默认基准里**；
它们被移到 [`tools/retired/`](tools/retired/)，只作为将来单独做边界测试时的素材。

**这套基准评测的是已保存的输出，不调用任何模型 API。** 它把预测里的卡片/分块单重新喂给
技能自己的三道门，再按标准答案做确定性检查。自动层不判断「版面观察是否属实」——
那一层只走人工评审（`engine/human_review.py`）。

## 当前状态

| 项目 | 状态 |
| --- | --- |
| 案例 | **24 条**：layout_core 10 / evidence_discipline 5 / partition 5 / input_modes 4 |
| 自动层 | 已实现：动作、两道门、六维评分、证据锚点、scope、习惯、分区、澄清、tool_log 真实性 |
| 人工层 | 已实现导出/回读接口；**尚未运行**，没有人工评分数据 |
| 模型运行 | **没有**。`predictions/fixtures/` 里是夹具，不是模型成绩 |
| 留出集 | `split: test` 3 条；其余为 development / validation |
| 真实学生草稿 | **没有**。全部是合成的文字还原或版面文字描述 |

## 快速开始

在 `draft-coach/bench/` 下：

```bash
# 1) 校验案例与标准答案
python3 schema_check.py

# 2) 跑基准自身的测试
python3 -m unittest discover -s tests -p 'test_*.py'

# 3) 生成夹具（不是模型输出），跑通评测
python3 make_fixture_predictions.py --mode oracle --out predictions/fixtures/oracle.json
python3 evaluate.py --predictions predictions/fixtures/oracle.json \
    --out reports/fixtures/oracle.report.json \
    --markdown reports/fixtures/oracle.report.md

# 4) 故意触发严重失败的夹具
python3 make_fixture_predictions.py --mode bad --out predictions/fixtures/bad.json
python3 evaluate.py --predictions predictions/fixtures/bad.json --strict

# 5) 导出人工评审表
python3 engine/human_review.py export \
    --predictions predictions/fixtures/oracle.json --out reviews/human.template.json
```

Windows 上 `python3` 可能是应用商店占位程序；本机用
`"D:/Program Files/anaconda3/python.exe"`。测试内部一律用 `sys.executable`。

退出码：**0** 报告已生成且达标 · **1** 低于 `--fail-under`，或 `--strict` 下有严重失败 ·
**2** 输入非法。`schema_check.py` 用 **0/1/2**（通过 / 数据不合格 / 输入非法）。

## 四个子集

| 子集 | 案例 | 权重 | 评什么 |
| --- | ---: | ---: | --- |
| `layout_core` | 10 | 40 | 六维版面分析：分区、挤行、划改、多路径、图形、留白 |
| `evidence_discipline` | 5 | 20 | 短草稿/信息不足时标不适用、缺原题写 scope、描述冲突先确认 |
| `partition` | 5 | 25 | 整张纸分块：块数、估计范围、uncertainty、确认问题、限制说明 |
| `input_modes` | 4 | 15 | 图片文字描述、无文字照片、多题分块、初中学段 |

## 预测文件长什么样

```json
{
  "arm": "skill_gates",
  "model": "your-model",
  "run_id": "2026-10-17-run-1",
  "predictions": [
    {
      "case_id": "LAY-01",
      "action": "analyze",
      "card": { "...六维卡..." },
      "reply": "交付给学生的教学语言（可选）",
      "tool_log": [
        {"command": "python3 scripts/validate_output.py validate --card card.json",
         "exit_code": 0},
        {"command": "python3 scripts/audit_output.py audit --card card.json --draft \"...\" --strict",
         "exit_code": 0}
      ]
    },
    {
      "case_id": "PAR-01",
      "action": "partition",
      "partition": { "...分块单..." },
      "tool_log": [
        {"command": "python3 scripts/partition_check.py validate --payload partition.json --strict",
         "exit_code": 0}
      ]
    },
    {
      "case_id": "INP-02",
      "action": "clarify",
      "reply": "请把你草稿里的文字打出来或口述一下。"
    }
  ]
}
```

- `action` 是 `analyze` / `partition` / `clarify`；评测器也保留 `refuse` 支持，
  但当前 24 条正面案例没有 refuse 出口。
- `tool_log` 在 `baseline` / `skill` 组可选；**有的话会被核对**：评测器重放门脚本，
  声称的退出码与实测不一致记为严重失败 `S_TOOL_LOG_MISMATCH`。
- **`skill_gates` 组必须记录真实跑过的门**：analyze 需要 `validate + audit`，
  partition 需要 `partition`。缺记录同样记 `S_TOOL_LOG_MISMATCH`。
  其他组该检查不适用，不进分母。clarify 不跑门，不要求 tool_log。
- 标准答案与案例分文件存放：`cases.jsonl` 只含输入与预期动作，
  `ground_truth.jsonl` 只含参考评分、锚点、习惯主题与分支标准。

## 评分怎么算

1. **案例分** = 该案例适用检查的加权平均（0–1）。某条检查不适用时记 `None`，不进分母。
2. **严重失败**（越界、编造无草稿分析、OCR 自读、分区断言、伪造工具记录等）**直接把该案例记 0**，
   不被其他检查抵消；同时单独列出，不参与加权。
3. **子集分** = 该子集案例分均值 × 100。
4. **总分** = 子集分按上表权重加权；分子集没有可评案例时重新归一化并写明。

读分时**必须同时看**：总分、硬门槛通过数、严重失败列表、覆盖度。
一个 87 分但带若干严重失败的运行，不是「良好的 87 分」。

### 严重失败代码

当前 24 条正面案例可触发的：

`S_MISSING_PREDICTION` · `S_MISSING_CARD` · `S_MISSING_OUTPUT` ·
`S_STRUCTURE_GATE` · `S_OUT_OF_SCOPE_CARD` · `S_ERROR_CLAIM` ·
`S_OCR_FABRICATION` · `S_PARTITION_ASSERTION` ·
`S_PARTITION_ERROR_CLAIM` · `S_TOOL_LOG_MISMATCH` ·
`S_BAIT_PRODUCED` · `S_REFUSE_WITH_OUTPUT`（clarify 却附带卡片）

评测器还保留 `S_NO_DRAFT_FABRICATION` 与 `S_WRONG_ROUTE`，供
[`tools/retired/`](tools/retired/) 的边界套件将来恢复时使用；当前正面案例不会触发。

## 已知的口径例外

这两条例外是**技能门本身已记录的边界**，不是评测放水：

- **`W_MULTI_PROBLEM_DRAFT`**：`_rules.py` 把带圈序号 `①②③` 当题号。学生用它们标
  「分类讨论的分支」或「方法①/②」时，`audit --strict` 会误报。相关案例
  （LAY-02/03/04/07/10）在 `ground_truth.jsonl` 的 `audit_warnings_allowed` 里显式放行
  这一条；其他 warning 仍会扣分。
- **INP-02 没有学生文字**：图片案例只给了版面描述。`audit --draft` 用这份版面描述
  （`input.audit_draft`），因为 audit 只用它做涂改/题号启发式；卡片内容仍必须
  写明「内容未经确认」。

## 这套评测做不到什么

- **两道门都不验数学**；本技能也不判断计算对错。结构与措辞通过不等于观察属实。
- **证据锚点只证明「卡片引用了草稿里出现过的位置或痕迹」**，不证明那处观察正确。
- **24 条是合成材料**，`draft_source` 多为文字还原；图片案例没有真实图片。
- **学段以高中为主**（初中 4 条），小学/大学未覆盖；`partition` 覆盖了
  `image_layout` 与 `student_text` 两种块来源，但没有真实图片。
- **自动层没有人工标注者参与**，因此不声称标注一致性或人工相关性。
- **权重未经试运行校准**；子集覆盖薄时高分不能外推。
- **人工层尚未运行**：`engine/human_review.py` 只提供接口与模板。

## 目录

```text
cases.jsonl / ground_truth.jsonl   案例与标准答案（交付物）
config.json                        权重、门脚本路径、严重失败代码
evaluate.py                        评分入口
schema_check.py                    数据自洽与防泄漏校验
make_fixture_predictions.py        oracle / bad / empty 夹具
engine/rules_bridge.py             按路径加载技能 scripts/_rules.py
engine/data.py                     数据加载
engine/gates.py                    重放三道门 + tool_log 核对
engine/checks.py                   逐案例检查
engine/scoring.py                  聚合、Wilson 区间、分层
engine/report.py                   Markdown 报告
engine/human_review.py             人工层导出 / 回读
schemas/                           case / prediction 的 JSON Schema
tools/                             数据集构建脚本（改案例后重建 JSONL）
tools/retired/                     已移出基准的边界/诱导案例（不参与构建与评分）
tests/                             44 项单元与端到端测试
predictions/fixtures/              夹具（不是模型输出）
reports/fixtures/                  夹具报告
reviews/                           人工评审文件（尚未运行）
```

## 改案例

改 `tools/data_*.py`，然后：

```bash
python3 tools/build_dataset.py
python3 schema_check.py
python3 -m unittest discover -s tests -p 'test_*.py'
python3 make_fixture_predictions.py --mode oracle --out predictions/fixtures/oracle.json
python3 evaluate.py --predictions predictions/fixtures/oracle.json \
    --out reports/fixtures/oracle.report.json --markdown reports/fixtures/oracle.report.md
python3 evaluate.py --predictions predictions/fixtures/bad.json --strict   # 应退出 1
```

**改完必须重跑真实输出**，不能凭印象写「应该会通过」。
`tools/build_dataset.py` 生成的两份 JSONL 是交付物；构建脚本只是重建入口。
