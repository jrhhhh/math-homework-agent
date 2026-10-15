# predictions/ —— 三组实验的原始输出

本仓库**没有配置任何模型 API**。`evaluate.py` 不会自己去调用模型。三组实验的输出必须由外部产出后保存到这里，评测器只负责加载、重放门脚本、算分。

## 文件契约

每个文件是 `schemas/prediction.schema.json` 的实例：

```json
{
  "arm": "skill_gates",
  "run_id": "2026-10-15-a",
  "producer": "host-agent:<名称>",
  "model_note": "模型与参数说明；无法核实精确版本时必须写明",
  "predictions": [
    {"case_id": "MATH-01", "response": "交付给学生的文字", "card": {…}, "tool_log": [
      {"command": "validate --card <tmp>/card.json", "exit_code": 0, "stdout": "…"}
    ]}
  ]
}
```

要点：

- `card` 没产出卡片时写 `null`（refuse / 追问 / 未过门）。
- `tool_log` 只在**真的跑过**门脚本时记录。`evaluate.py` 会把 `card` 重新喂给门脚本（现在是两个：`../scripts/validate_output.py` 与 `../scripts/audit_output.py`），比对声称的退出码：**对不上就记为严重失败 S5（伪造工具执行记录）**。
- `producer` 以 `fixture` 开头的文件会被报告标成「不是模型运行结果」（`is_model_run: false`），并打警告。

## 三组

| arm | 加载 SKILL.md | 跑门脚本 | 目录建议 |
| --- | --- | --- | --- |
| `baseline` | 否 | 否 | `predictions/baseline.<run>.json` |
| `skill` | 是 | 否 | `predictions/skill.<run>.json` |
| `skill_gates` | 是 | **是** | `predictions/skill_gates.<run>.json` |

## 夹具（fixtures/）

`fixtures/` 下的文件由 `make_fixture_predictions.py` 生成，**不是模型结果**，只用于验证评测流程本身跑得通（含故意编造证据与谎报退出码的反例）。不要把它们写进任何成绩结论。

```bash
python3 evals/make_fixture_predictions.py --mode oracle     --arm skill_gates --out predictions/fixtures/oracle.skill_gates.json
python3 evals/make_fixture_predictions.py --mode empty      --arm skill       --out predictions/fixtures/empty.skill.json
python3 evals/make_fixture_predictions.py --mode fabricated --arm skill_gates --out predictions/fixtures/fabricated.skill_gates.json
```

## 还没有的东西

**本批没有任何真实模型输出。** `predictions/` 里除夹具外为空，因此评分报告里三组实验都标为「未运行」，见 [../reports/README.md](../reports/README.md)。要产出真实输出，需要一个能读 `SKILL.md`、按流程作答、并能执行本机门脚本的宿主 agent（或用你自己的模型管线），逐条处理 `cases.jsonl` 里的 `input.prompt`。
