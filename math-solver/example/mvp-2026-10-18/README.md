# Math Solver 最小可行性测试（2026-10-18）

用五类题各 1 道进行一次端到端测试：按 [SKILL.md](../../SKILL.md) 生成契约内 JSON，再用结构门逐份校验。

## 输入与答案

| # | 类别 | 题目 | 输出答案 |
| --- | --- | --- | --- |
| 1 | 基础计算与方程 | 解方程 2/(x-1)+1=x/(x+1) | x=-1/3 |
| 2 | 函数与不等式 | f(x)=√(x²-2x-3)，求定义域并解 f(x)≥0 | 定义域与解集均为 (-∞,-1]∪[3,+∞) |
| 3 | 数列 | 等差数列 a₁=2，a₄+a₆=20，求 aₙ 与 Sₙ | aₙ=2n，Sₙ=n(n+1) |
| 4 | 含参与分类讨论 | 解 ax-1>0（a 为参数） | a>0：x>1/a；a=0：无解；a<0：x<1/a |
| 5 | 易错与异常输入 | 若 √(x²)=4，求 x，并思考易忽略的情况与增根 | x=±4；易把 √(x²) 写成 x 而漏负根；本题平方不产生增根 |

对应输出文件：

- `01_rational_equation.json`
- `02_domain_and_inequality.json`
- `03_arithmetic_sequence.json`
- `04_parameter_inequality.json`
- `05_sqrt_square_absolute.json`

## 结构门结果

五份都带 `--strict` 运行，退出码均为 **0**，无 error、无 warning：

```text
01_rational_equation.json            exit 0  通过
02_domain_and_inequality.json        exit 0  通过
03_arithmetic_sequence.json          exit 0  通过
04_parameter_inequality.json         exit 0  通过
05_sqrt_square_absolute.json         exit 0  通过
```

复现（在 `math-solver/` 目录）：

```bash
for f in example/mvp-2026-10-18/*.json; do
  python3 scripts/validate_output.py validate --card "$f" --strict
done
```

Windows 上若 `python3` 是应用商店占位程序，请换成实际解释器路径。

## 独立数值核对

结构门不验数学；以下是另外执行的核对结果：

- **Q1**：x=-1/3 代回，左边与右边都等于 -1/2。
- **Q2**：x=-2, -1, 3, 4 时根号内非负；x=0 时根号内为 -3，确实不在定义域。端点 -1、3 可取。
- **Q3**：a₁…a₆ = 2,4,6,8,10,12；a₄+a₆=20；Sₙ=n(n+1) 在 n=1..6 与直接求和一致。
- **Q4**：a=2 时 x=1 成立、x=0 不成立；a=-2 时 x=-1 成立、x=0 不成立；a=0 时 -1>0 为假。
- **Q5**：x=4 与 x=-4 都有 √(x²)=4。

这些是代回与有限点检查，不是一般性证明；它们只说明本次答案在检查覆盖的范围内成立。
