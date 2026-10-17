# 预测文件约定

`evaluate.py` 读取一个 JSON 文件，里面是**已保存的模型输出**。它不调用模型，
也不重试；一次评测对应一份文件。

## 顶层

```json
{
  "arm": "baseline | skill | skill_gates",
  "model": "模型名或产出方",
  "run_id": "可追踪的运行标识",
  "generated_at": "2026-10-17",
  "predictions": [ ... ]
}
```

`arm` 只是报告里的标签，评测器不据此改变评分。推荐三个对照：

| arm | 加载 SKILL.md | 跑门脚本 |
| --- | --- | --- |
| `baseline` | 否 | 否 |
| `skill` | 是 | 否 |
| `skill_gates` | 是 | 是，并在 `tool_log` 里记录真实退出码 |

## 每条预测

```json
{
  "case_id": "LAY-01",
  "action": "analyze",
  "card": {},
  "partition": null,
  "refusal": null,
  "reply": "交付给学生的文字（可选）",
  "tool_log": [
    {"command": "python3 scripts/validate_output.py validate --card card.json",
     "exit_code": 0}
  ]
}
```

- `action`：`analyze` / `partition` / `clarify`。评测器也保留 `refuse` 支持，
  但当前 24 条正面案例没有 refuse 出口。
- `card`：只有 `analyze` 用；必须符合 `../references/output-schema.md`。
- `partition`：只有 `partition` 用；必须符合 `../references/partition.md`。
- `refusal`：只有 `refuse` 用，`{"reason": "...", "message": "..."}`；当前案例不使用。
- `reply`：`clarify` 必填；`analyze` 可填交付给学生的教学语言，供人工层参考。
- `tool_log`：`baseline` / `skill` 组可选，`skill_gates` 组**必填**。有的话会被逐条
  核对退出码；`skill_gates` 组缺少记录会记 `S_TOOL_LOG_MISMATCH`。

## tool_log 的真实性

评测器会：

1. 把 `card` / `partition` 重新喂给技能自己的门脚本；
2. 从 `command` 里识别子命令（`validate_output` / `audit_output` / `partition_check` / `refuse`）；
3. 看 `audit` / `partition` 命令里有没有 `--strict`；
4. 把 `exit_code` 与实测值比对。

**对不上就是 `S_TOOL_LOG_MISMATCH`。** 不要手写「应该是 0」；记录真实运行的退出码。
没有跑门就留空数组或不给 `tool_log`，不要伪造。

同一子命令出现多次时，评测器**取最后一次**：重试后交付的是最终那次门运行。
如果你把三次尝试都记下来，请确保最后一条对应最终卡片。

`refuse` 的退出码按技能约定是：`empty` → 2，`unreadable` → 2，`out_of_scope` → 1。
仅当你恢复了 `tools/retired/` 的边界套件时才需要记录；当前正面案例不跑拒绝出口。

## 夹具

`fixtures/` 里的三份文件由 `../make_fixture_predictions.py` 生成：

- `oracle.json`：用标准答案拼出的合法输出，用来证明流程可跑；
- `bad.json`：故意触发严重失败，用来证明评测器抓得住；
- `empty.json`：没有预测，用来证明空跑是 0 分而不是满分。

它们是**夹具，不是模型成绩**。报告里的 `arm` 会带 `fixture-` 前缀。
