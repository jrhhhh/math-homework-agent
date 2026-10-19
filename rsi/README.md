# math-solver RSI 工具

对应 [plan.md](../plan.md)。本目录把 `math-solver` 技能本身当作可优化对象；
**不改变**学生面向的调度规则，也不是学生解答的优化卡。

## 当前实现范围

| 模块 | 状态 | 说明 |
| --- | --- | --- |
| `runner.py` | 已实现 | 加载技能版本，在固定预算下运行单题，记录预测与真实结构门退出码 |
| `grade.py` | 已实现 | 复用 `math-solver/bench/engine` 计算 `g(a)`；支持多份 predictions 视为多个种子 |
| `config.json` | 已实现 | 预算、接受阈值、可编辑/冻结路径 |
| `validate_diff.py` | 已实现 | 路径白名单、行数上限、冻结路径对比 |
| `outer.py` | 已实现 | 外层接口：夹具 / Python 函数 / stdin-stdout 命令 |
| `loop.py` | 已实现 | 算法 1：评分、接受、归档、argmax incumbent、patience 停止 |
| `splits_check.py` | 已实现 | 四份 split 自洽、跨集合泄漏、bench 污染检查 |
| `adapters/` | 已实现 | 本机 `claude` CLI 内层 / 外层 adapter |
| `baselines/a_0/` | 已实现 | 精简版技能，作为 RSI 起点；当前 `math-solver` 是 `a_human` |
| `splits/build_splits.py` | 已实现 | 生成四份 split 的 cases / ground truth / manifest |
| `splits/tools/verify_math.py` | 已实现 | 122 项数学事实与标准答案核验 |
| `splits/` | 已填入 | selection 26 / sealed_id 6 / ood 4 / probes 8 |

`runner.py` 不做数学评分；`grade.py` 不做接受判定。两者分开，便于用夹具验证管线。

## 快速开始

在仓库根目录（Windows 上用 Anaconda 的 Python）：

```bash
PY="D:/Program Files/anaconda3/python.exe"

# 1) 用 oracle 夹具跑一遍 runner（会重放结构门）
"$PY" rsi/runner.py --fixture d:/tmp/rsi/oracle.json \
    --out d:/tmp/rsi/oracle.runner.json

# 2) 评分：应得到 g = 1.0、0 严重失败
"$PY" rsi/grade.py --predictions d:/tmp/rsi/oracle.runner.json

# 3) bad 夹具：应得到 g ≈ 0.7611、12 类严重失败
"$PY" rsi/grade.py --predictions d:/tmp/rsi/bad.json --strict-severe
# 退出码 1

# 4) 校验一版技能改写（只允许 SKILL.md 与 references/*.md）
"$PY" rsi/validate_diff.py --base math-solver --candidate runs/a001/math-solver

# 5) 回归测试
"$PY" -m unittest discover -s rsi/tests -p 'test_*.py'

# 6) 夹具驱动的循环冒烟（所有候选都用同一份 predictions，因此不会接受）
"$PY" rsi/loop.py --base-skill math-solver \
    --inner-fixture d:/tmp/rsi/oracle.json \
    --outer-fixture d:/tmp/rsi/outer.json \
    --run-dir d:/tmp/rsi/run-smoke --steps 1 --seeds 1
```

`--inner-fixture` 只用于冒烟；真实运行用 `--inner-command` 接模型，
外层用 `--outer-command` 接提出候选目录的智能体。外层请求里**没有标准答案**，
只有选拔题输入、脱敏失败摘要、预算与可编辑面。

## split 检查

四份 split 的目录约定与硬规则见 [splits/README.md](splits/README.md)。

```bash
"$PY" rsi/splits_check.py validate --root rsi/splits
```

退出码：0 = 通过；1 = 不合格；2 = 输入非法。当前四份内容尚未填写，
因此会以 `E_MISSING_SPLIT` / `E_EMPTY_SPLIT` 退出 1，这是预期状态。

> 注意：`runner.py` 会用真实结构门结果**覆盖** adapter 自报的 `tool_log`。
> 因此 bad 夹具里的“伪造退出码”如果经过 runner 会被纠正；要复现 76.11，
> 应直接把夹具交给 `grade.py`，不要先经过 runner。

## Adapter 协议

真实模型接入有三种方式：

1. **`CallableAdapter`**：在 Python 里包装一个函数，输入 `RunRequest`，输出预测 dict。
2. **`CommandAdapter`**：任意可执行程序，stdin 收 JSON 请求，stdout 返回 JSON 预测。
   ```bash
   "$PY" rsi/runner.py --command '["python","my_adapter.py"]' \
       --out d:/tmp/rsi/real.json
   ```
3. **`FixtureAdapter`**：回放已保存的预测，只用于测试。

请求字段：

```json
{
  "case": {"case_id": "...", "input": {"problem": "..."}, "...": "..."},
  "skill_root": "/abs/path/to/math-solver",
  "skill_fingerprint": "sha256...",
  "skill_text": "SKILL.md + references/*.md 的拼接",
  "budget": {"max_tokens": 60000, "max_tool_calls": 20,
             "max_seconds": 600.0, "max_cost_usd": null}
}
```

预测字段：

```json
{"action": "solve", "output": { "...solution JSON..." },
 "usage": {"total_tokens": 12345, "tool_calls": 4, "cost_usd": 0.02}}
{"action": "route", "route_to": "math-error-diagnosis", "reply": "..."}
{"action": "clarify", "reply": "..."}
null
```

- `usage` 可省略；省略时只按墙钟时间判超预算。
- `runner` 会丢弃 route / clarify 附带的 `output`，并记 `runner_notes`。
- 超过预算不会被静默截断，而是标记 `over_budget: true`；外层循环应拒绝这样的候选。

## g(a) 的口径

```text
r_priv_t = 单题私有分（bench 的逐案例分，0–1）
g(a)     = 所有题、所有种子的总分均值 / 100
```

`grade.py` 额外报告：

- `severe_count_max`：所有种子中最坏的严重失败数；
- `severe_failures`：逐条严重失败；
- `subset_scores_mean`：四子集均分；
- `total_min` / `total_max`：种子间波动，用来判断信号是否大于噪声。

接受规则不在 `grade.py` 里；按 `config.json` 的 `acceptance.delta` 由未来的 `loop.py` 执行。

## 真实运行（本机 claude CLI）

内层用 `deepseek-v4-flash`（较小），外层用 CLI 当前默认模型（较强），
对应论文“外层强、内层便宜”的设置：

```bash
PY="D:/Program Files/anaconda3/python.exe"

CLAUDE_INNER_MODEL=deepseek-v4-flash "$PY" rsi/loop.py \
    --base-skill rsi/baselines/a_0 \
    --cases rsi/splits/selection/cases.jsonl \
    --ground-truth rsi/splits/selection/ground_truth.jsonl \
    --bench-config math-solver/bench/config.json \
    --config rsi/config.json \
    --run-dir d:/tmp/rsi/run-001 \
    --steps 10 --seeds 1 --patience 5 \
    --inner-command '["D:/Program Files/anaconda3/python.exe","rsi/adapters/claude_inner.py"]' \
    --outer-command '["D:/Program Files/anaconda3/python.exe","rsi/adapters/claude_outer.py"]'
```

可用环境变量：

- `CLAUDE_INNER_MODEL`：内层模型；不设则用 CLI 当前配置。
- `CLAUDE_OUTER_MODEL`：外层模型；不设则用 CLI 当前配置。
- `CLAUDE_INNER_MAX_BUDGET_USD` / `CLAUDE_OUTER_MAX_BUDGET_USD`：单次调用美元上限。
- `CLAUDE_BIN`：`claude` 可执行文件路径。

adapter 不启用任何模型侧工具，因此模型不会执行 Python/SymPy，也不应声称执行过；
所有文件写入由 adapter 自己的 Python 代码完成。外层只返回 find/replace edits，
`validate_diff.py` 仍会检查路径、行数与冻结目录。

### 首轮基线（2026-10-19，1 个种子，仅作管线检查）

26 题选拔集（20 道新题 + 6 道 2024 新高考Ⅰ卷硬题）：

| 内层模型 | `a_0` | `a_human` | 严重失败 |
| --- | ---: | ---: | --- |
| `deepseek-v4-flash` | 94.10 | 94.53 | 各 1 |
| CLI 默认（较强） | 97.99 | 96.80 | 0 |

这些是单种子读数，不能当作稳定准确率；它们只用于确认“有提升空间、评分链路可用”。

## 与评分器的边界

- `runner.py` 只重放结构门；不判断数学。
- `grade.py` 复用 bench 的确定性检查；它同样**不验证推导是否严谨**。
- 关键词核验、答案形态检查都可以被钻空子；最终结论仍需人工层与诚实性探针。
