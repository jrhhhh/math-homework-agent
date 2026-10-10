# modexp-skill（课堂最小示例）

《数学智能体工程与实践》第 4 讲动手环节的配套示例：一个按"五步法"建设的最小完整技能，用于**模幂与乘法阶的计算与独立核验**。

## 结构

```
modexp-skill/
├── SKILL.md                  ← 入口（触发器 + 纪律 + 工作流 + 红线）
└── scripts/
    └── modexp_check.py       ← 确定性操作脚本（纯标准库，无依赖）
```

## 快速体验

```bash
python3 scripts/modexp_check.py compute --base 7 --exp 256 --mod 13
python3 scripts/modexp_check.py verify  --base 7 --exp 256 --mod 13 --claim 9   # 接受，退出码 0
python3 scripts/modexp_check.py verify  --base 7 --exp 256 --mod 13 --claim 5   # 驳回，退出码 1
python3 scripts/modexp_check.py order   --base 7 --mod 13                       # 阶 12，是原根
```

## 给 agent 的安装 / 测试提示词

> 请把 `examples/modexp-skill/` 作为技能安装到你的技能目录，然后用它完成冒烟测试："计算 2^1000 mod 1009，并核验我声称的结果是 562——告诉我裁决与证据。"

（提示：562 是故意给错的，正确的 agent 应当调用 `verify`、收到 `accepted: false`、报告 `actual` 的真实值，而不是附和用户。）
