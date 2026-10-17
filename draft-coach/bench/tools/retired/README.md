# 已移出基准：边界与诱导案例

这里的 `data_boundary.py` 与 `data_adversarial.py` 是 2026-10-17 版基准最初包含的
10 条**越界/拒绝**案例（无草稿、正式解答、只问对错、变式题、评分、整题重写、OCR 等）。

它们**不在当前基准里**：当前基准只评正面能力——六维版面分析、证据纪律、整页分区、
输入形态。`tools/build_dataset.py` 不再导入这两个文件，`cases.jsonl` /
`ground_truth.jsonl` 也不含这些案例。

保留它们的原因：这些边界仍然写在 `SKILL.md` 与 `scripts/_rules.py` 里。
它们只作为**历史素材**保留，恢复前需要同时恢复评测器里的 `reply_decline` 检查与
对应的 gold 字段；**不要**把这两个文件重新加入默认基准，也不要用它们给当前
benchmark 凑案例数。
