# RSI 数据划分

对应 [plan.md](../../plan.md) §3.2–3.3。四份 split 的用途严格分开：

| 目录 | 用途 | 是否参与外层选择 | 要求 |
| --- | --- | --- | --- |
| `selection/` | 循环内计算 `g(a)` | 是 | 可复用现有题，但必须在 manifest 里标污染状态 |
| `sealed_id/` | 同任务族、未参与选择的最终验收 | 否 | **必须是新题**，不得复用 bench 的 case_id 或题目 |
| `ood/` | 分布外任务族的最终验收 | 否 | **必须是新题**，任务族不在 selection 中 |
| `probes/` | 诚实性探针（假核验 / 假工具 / 歧义题） | 否 | **必须是新题**，不进入 `g` |

每份 split 的目录结构：

```text
selection/
  cases.jsonl          # 与 math-solver/bench 同 schema；split 字段写 selection
  ground_truth.jsonl   # 与 cases 一一对应
  manifest.json        # 来源、日期、污染状态
```

## 硬规则

1. **case / ground truth 一一对应**，字段与 `math-solver/bench/schema_check.py` 一致。
2. **跨 split 不得重复**：`case_id` 与完整 `input` 都不能相同。
3. **`sealed_id` / `ood` / `probes` 不得复用现有 bench**：既不能复用 `MATH-*` 的
   `case_id`，也不能复用相同题面。现有 51 条都参与过技能开发，不能当留出集。
4. **这三份的 manifest 不得写 `contaminated: true`**；写了直接判不合格。
5. **缺 manifest 只是 warning**，但缺来源记录会让“新题”无法审计。
6. 检查器**不验数学**，也不判断题目是否真的独立；来源与标准答案仍需人工复核。

## 使用

```bash
PY="D:/Program Files/anaconda3/python.exe"
"$PY" rsi/splits_check.py validate --root rsi/splits \
    --json-out d:/tmp/rsi/splits.report.json
```

退出码：0 = 通过；1 = 不合格；2 = 输入非法。

当前 `rsi/splits/` 只有说明与模板，**四份 split 都还没有内容**；在填入新题之前，
检查器会以 `E_MISSING_SPLIT` / `E_EMPTY_SPLIT` 退出 1。这是预期状态。

## 探针标签建议

`probes/tags` 里可以写：

- `probe:no_tool`：不提供 Python/SymPy，正确行为是不声称工具核验；
- `probe:ambiguous`：条件不足，正确行为是 `needs_clarification`；
- `probe:false_verification`：有诱饵捷径，测是否谎称已核验；
- `probe:keyword_bait`：测是否只堆砌核验关键词。

这些标签只用于报告分组，不改变评分逻辑。

## manifest 模板

见 [manifest.template.json](manifest.template.json)。复制到每份 split 目录后改名
为 `manifest.json`，并把 `source` 与 `created_at` 填实。
