# 基线技能

| 目录 | 对应论文 | 说明 |
| --- | --- | --- |
| `a_0/` | AIDE0 | 当前 `math-solver` 的精简起点：保留职责边界、工作流、安全规则与输出契约，删去较长的说明与教学备注指导 |
| `../math-solver/` | AIDEhuman | 当前人工编写的完整技能，作为强基线；不复制，直接以 `--skill math-solver` 运行 |

`a_0` 只包含 `SKILL.md` 与 `references/`，没有 `bench/`、`scripts/`、`tests/`、`example/`。
RSI 循环只允许改 `SKILL.md` 与 `references/*.md`；结构门始终使用生产目录
`math-solver/scripts/validate_output.py`，不会使用候选目录里的脚本。

首轮基线（26 题选拔集、1 个种子）见 [../README.md](../README.md) 的“真实运行”一节。
