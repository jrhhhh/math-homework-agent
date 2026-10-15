# 留出集（hidden test set）——本批为 0 条

**本轮没有留出集案例。** 现有的 38 条全部落在 development（25）与 validation（13）。

## 为什么空着

- 正式版目标是 380 条。本批优先把 development / validation 做扎实；留出集应当由**没有参与过案例设计的人**撰写，否则会带上同一套作者偏见，测不出泛化。
- 一个案例一旦被设计者自己拿来调过提示词或改过评分口径，它就不再是留出集了。

## 怎么加（加载器已支持）

案例与标准答案分放两个文件，各加一行，`split` 填 `test`：

- `cases.jsonl` 加一行（输入侧：`case_id` / `subset` / `split` / `input` / `expected_action` …）
- `ground_truth.jsonl` 加一行（答案侧：`gold_errors` / `gold_correct_steps` / `gold_dimensions` …）

两份文件的 `case_id` 必须同集同序，否则校验器报 `E_GT_MISSING` / `E_GT_ORPHAN`。评测时加 `--splits development validation test` 即可纳入。

## 防泄漏规则

`template_id` 是划分的最小单位：**同一模板（含只换数字的近重复）必须整体落在同一个 split**。校验器会拒收跨 split 的同模板案例：

```bash
python3 draft-coach/evals/engine/schema_check.py
```

预留的留出集模板号见 [`holdout_templates.json`](holdout_templates.json)：写新案例时**不要**用这些模板号，它们留给留出集作者。

## 留出集应当包含什么

按 [docs/DESIGN.md](docs/DESIGN.md) §1，测试集必须同时包含正确草稿、真实错误、边界案例与对抗性案例。本批已有的对抗性设计（假错诱饵、已纠正的旧笔迹、缺原题、图像歧义、跨块误配、注入指令）应当在留出集里**换一批新模板**重现，而不是照抄。
