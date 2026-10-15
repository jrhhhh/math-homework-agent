# reviews/ —— 模型辅助层与人工层的评审文件

**本目录当前为空（除本文件）：这两层都还没跑。** 没有评审文件时，报告把这两层记为「未运行」，**不是 0 分**，也不进子集分。

## 怎么产出

```bash
# 模型辅助层（由独立上下文的评审按固定评分卡填写）
python3 evaluators/human_review.py export --layer model_assisted --arm skill_gates \
    --out reviews/skill_gates.model_assisted.json

# 人工层
python3 evaluators/human_review.py export --layer human --arm skill_gates \
    --out reviews/skill_gates.human.json

# 填完后回读（0 = 全部评完；1 = 有效但还有 null；2 = 非法输入）
python3 evaluators/human_review.py check --review reviews/skill_gates.human.json

# 计分
python3 runners/run_suite.py --predictions predictions/skill_gates.json \
    --review reviews/skill_gates.human.json --review reviews/skill_gates.model_assisted.json
```

## 填写规则

- 只能填 `true` / `false`。**`null` 表示还没评**，与 `false` 不是一回事：它不进分母。
- 只有该层该管的指标会被列出（`configs/default.json` 的 `metric_layers` 决定）。
- 评之前**先把那道题自己算一遍**。这些指标要回答的正是自动层答不了的问题：
  - `evidence_support_rate`：证据确实在草稿上，但它**能不能支持**那条结论（例如引用正确的移项，却断言这里除法出错）。
  - `explanation_correctness` / `fix_correctness`：错因与最小修改在数学上是否成立。
  - `dimension_evidence_grounded`：六维的观察与证据是否出自草稿，有没有编造涂改、试错、图形。
  - `clarify_quality`（追问是否问到点上）、`multi_problem_handling`、`evaluable_scope_respected`、`mixed_content_reading`。
  - `retry_policy_followed`（`human` 层）：未过门时是否定点修改且不超过 3 轮——需要完整 transcript，本批未采集。

## 边界

这些是**评审判断**，不是 ground truth，也不等于自动验证。报告里与自动指标分开列。`run_suite.py` 会把非布尔值直接拒收（退出码 2），避免把半个评分悄悄算成评分。
