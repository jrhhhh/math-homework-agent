# 任务：独立评审一批「草稿检查」回答（模型辅助层）

你在填这套 benchmark 的**模型辅助层**：自动指标算不了的东西——证据是否**支持**结论、
错因解释是否成立、改法对不对、六维观察是否属实。你填的是结构化判定，**不是** ground
truth，报告里会单列。

## 只许读这些

- 分配给你的盲评包（在 `reviews/in/<bundle_id>.json`）
- `draft-coach/evals/docs/ANNOTATION_GUIDE.md`（评分口径，必读）

## 绝对不许读

- `draft-coach/evals/runs/2026-10-15/reviews/mapping.json`（那会告诉你这条来自哪个实验组）
- `draft-coach/evals/runs/2026-10-15/out/`（产出代理的目录）
- `draft-coach/evals/cases.jsonl`、`ground_truth.jsonl`、`config.json`
- `reviews/out/` 下**别人**的结果

你在盲评：**不知道**这条来自哪个实验组，也不该猜。包里的 `bundle_id` 是随机哈希，
不是案例编号。

## 一个包里有什么

| 字段 | 含义 |
| --- | --- |
| `student_input` | 学生给的东西（题面、草稿、最终解答、学段） |
| `reference` | 参考答案：`gold_errors`（每条带 `evidence_anchor` 与 `minimal_fix`）、`gold_correct_steps`、`gold_dimensions`、`expected_action`、`unevaluable_scope` 等 |
| `answer_under_review` | 被评的回答：`response`（给学生的话）与 `card`（卡片 JSON，可能为 `null`） |
| `metrics_to_rate` | 本题要你判的指标，每个附判据 |
| `null_rule` | 何时写 `null`（**必读**，null 与 false 不是一回事） |

## 判的步骤（顺序不能颠倒）

1. **自己把这道题算一遍。** 先不看被评回答，按题面与草稿独立核对每一步：
   哪一步成立、哪一步不成立、正确结果是什么。这一步不做完，后面全是空转。
2. 再读 `answer_under_review`，与你在第 1 步的结论对照。
3. 逐指标判 `true` / `false` / `null`（只用这三个值，布尔值不要加引号）。
4. 每个包写一句 `notes`：你的关键判断依据，尤其是判 `false` 的那几条。

## 判的时候容易犯的错

- **按文字长短、语气好坏判**——不要。只判实质。
- **把「没提到」当成「说错了」**——没提到的内容不进你的判定；只有说错了才判 false。
- **把锚点字符串出现当成结论正确**——证据在草稿里出现 ≠ 结论成立。把对的判成错，
  `evidence_support_rate` 就是 false。
- **对没有对象的指标硬给 false**——例如答案一处错都没报时，「改法对不对」写 `null`。
- 被评回答里若是**自由文字**（没有卡片），也能判：判它有没有指出那处错误、
  给的改法对不对、解释成不成立。

## 输出

每个包写一份 `draft-coach/evals/runs/2026-10-15/reviews/out/<bundle_id>.json`：

```json
{
  "bundle_id": "<原样照抄包里的 bundle_id>",
  "ratings": {"<指标名>": true, "<指标名>": false, "<指标名>": null},
  "notes": "关键依据；判 false 的写清为什么"
}
```

`ratings` 必须**恰好覆盖包里 `metrics_to_rate` 的全部指标名**，不多不少。
