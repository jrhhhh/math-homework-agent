# solution-refiner 正解优化器

原作来自本仓库 `solution_refiner` 分支提交 `759a554c62c598dcd28e51c6194080058ae5fc41`。此目录是协作对齐版本，原分支保持不变。

只优化已经核验成立的完整解答。项目先调用 math-error-diagnosis，由宿主核验交接状态和解答版本，再生成四字段、三个方向的优化卡。诊断报告不放进优化卡。

从本目录运行：

```bash
python3 solution_card_check.py validate --card example/correct_card.json
python3 solution_card_check.py audit --card example/correct_card.json --solution '用求根公式：x=(5±√1)/2，所以 x1=3，x2=2。' --problem '求 x²-5x+6=0 的根。' --strict
```

mixed_diagnosis_card.json用于展示审计拒绝混入诊断的卡片。mathematically_wrong_card.json故意包含错误因式分解，仍可过格式/措辞门，用于说明两门不检查数学正确性。宿主必须另审数学和实际改进。

完整使用规则见 [SKILL.md](SKILL.md)；共用调度见 [AGENTS.md](../AGENTS.md)。
