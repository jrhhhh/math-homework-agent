# 三组真实运行结果

| 条件 | 已完成/30 | 最终门通过 | 首次门通过 | 修正成功 | 模型调用数 | 累计调用秒数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 30 | 28 | 28 | 0 | 30 | 811.268 |
| skill | 30 | 29 | 29 | 0 | 30 | 870.077 |
| skill_gates | 30 | 29 | 29 | 0 | 32 | 904.335 |

累计秒数为各调用时间之和，不是并发实验的墙钟时间。

## 匿名模型辅助复核

| 条件 | 数学正确 | 首错定位 | 模式遵守 | 有据不编造 | 教学可用 |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline | 24/24 | 11/11 | 30/30 | 29/30 | 30/30 |
| skill | 24/24 | 11/11 | 30/30 | 29/30 | 30/30 |
| skill_gates | 24/24 | 11/11 | 30/30 | 29/30 | 30/30 |

不适用项不进分母；0/0 表示尚无评分。逐项 Wilson 95% 区间见 summary.json。
同一模型不同上下文核验，不能作为人类、异模型或形式化验证。

## 未通过项与解释

| 案例 | 条件 | 门 | 含义 |
| --- | --- | --- | --- |
| C25 | baseline | scripts/audit_output.py | 多题草稿走单题分析，严格门要求先分区并确认；当前工作台已修正路由，冻结结果保留 |
| C25 | skill | scripts/audit_output.py | 多题草稿走单题分析，严格门要求先分区并确认；当前工作台已修正路由，冻结结果保留 |
| C25 | skill_gates | scripts/audit_output.py | 多题草稿走单题分析，严格门要求先分区并确认；当前工作台已修正路由，冻结结果保留 |
| C28 | baseline | scripts/audit_output.py | 草稿卡使用了评分措辞，越界审计拒绝 |

本次最终门通过数差异（29/30 对 28/30）只来自 C28 基线输出被措辞门拒绝；三组模型辅助盲评汇总相同，不能据单次30题结果认定 Skill 带来准确率增益。C25 三组都失败，说明多题版面入口需要先做分区确认。重跑输出是对初始服务中断项的恢复，不是独立重复实验。

## 人工复核

用户于2026-10-22明确选择本次先交付模型辅助评测，真人复核列为后续工作。已提供匿名10题复核包，空模板不计分。

## 证据范围

Saved single-run course cases; model-assisted review is same-model separate-context, not human or formal verification. Gate pass is not mathematical accuracy.
Token usage recorded; no verified monetary billing data available.
每条件一次，案例为人工编写；不据此声称普遍准确率或稳定增益。
