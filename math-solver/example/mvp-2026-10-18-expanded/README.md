# Math Solver 扩充测试（2026-10-18）

五类共 25 道题，每类 5 道。按 [SKILL.md](../../SKILL.md) 逐题生成契约内 JSON，再统一过结构门；数学结论另用 `verify_math.py` 做符号/数值核对。

## 结果汇总

| 检查 | 结果 |
| --- | --- |
| 结构门 `validate --strict` | **25/25 通过**，无 error、无 warning |
| 数学核验 `verify_math.py` | **44/44 检查通过** |
| 技能自带单元测试 | 20/20 通过（`math-solver/tests/`） |

结构门只查 JSON 形状与状态一致性；数学核验是测试辅助脚本，不替代一般性证明。

## 参考答案核对

用户提供的参考答案中有 **6 题需要修正**（1.3、1.4、1.5、2.5、3.3、4.2），其余 **19 题一致**；其中 4.3 只是边界归属写法不同，数值等价。逐项代回证据见 [reference_check.md](reference_check.md)。

## 逐题结果

### 一、基础计算与方程

| # | 题目 | 答案 | 文件 | 门 |
| --- | --- | --- | --- | --- |
| 1.1 | 3(x+2)-5=2x | x=-1 | `c1_01_linear_equation.json` | 0 |
| 1.2 | x²-5x+6=0 | x=2 或 3 | `c1_02_quadratic_equation.json` | 0 |
| 1.3 | 3/x=x-2 | x=3 或 -1 | `c1_03_reciprocal_equation.json` | 0 |
| 1.4 | √(2x+1)=x-1 | x=4 | `c1_04_radical_equation.json` | 0 |
| 1.5 | x/(x-2)+1/(x+2)=8/(x²-4) | x=-5 | `c1_05_rational_equation.json` | 0 |

### 二、函数与不等式

| # | 题目 | 答案 | 文件 | 门 |
| --- | --- | --- | --- | --- |
| 2.1 | f(x)=√(x-2) 的定义域 | [2,+∞) | `c2_01_sqrt_domain.json` | 0 |
| 2.2 | x²-x-2<0 | (-1,2) | `c2_02_quadratic_inequality.json` | 0 |
| 2.3 | f(x)=ln(x+1)/(x-3) 的定义域 | (-1,3)∪(3,+∞) | `c2_03_log_domain.json` | 0 |
| 2.4 | f(x)=x²-2ax+1 在 [0,2] 的单调性 | a≤0 递增；0<a<2 先减后增；a≥2 递减 | `c2_04_monotonicity_parameter.json` | 0 |
| 2.5 | (x-1)/(x+2)≥2 | [-5,-2) | `c2_05_rational_inequality.json` | 0 |

### 三、数列、三角函数或几何

| # | 题目 | 答案 | 文件 | 门 |
| --- | --- | --- | --- | --- |
| 3.1 | 等差数列 a₁=1，d=3，求 a₅ | a₅=13 | `c3_01_arithmetic_term.json` | 0 |
| 3.2 | △ABC 中 A=π/3，b=2，c=3，求 BC | BC=√7 | `c3_02_cosine_rule.json` | 0 |
| 3.3 | 等比数列 a₁=2，a₃=8，求 S₅ | q=2 时 62；q=-2 时 22 | `c3_03_geometric_sum.json` | 0 |
| 3.4 | y=2sin(2x+π/4) 的递增区间 | [kπ-3π/8, kπ+π/8]，k∈Z | `c3_04_sine_monotonicity.json` | 0 |
| 3.5 | a cos B+b cos A=2c cos C，求 C | C=π/3 | `c3_05_triangle_identity.json` | 0 |

### 四、含参与分类讨论

| # | 题目 | 答案 | 文件 | 门 |
| --- | --- | --- | --- | --- |
| 4.1 | kx+2>0 | k>0：x>-2/k；k=0：R；k<0：x<-2/k | `c4_01_linear_parameter.json` | 0 |
| 4.2 | (x-a)(x-2)>0 | a<2：x<a 或 x>2；a=2：x≠2；a>2：x<2 或 x>a | `c4_02_quadratic_parameter_inequality.json` | 0 |
| 4.3 | f(x)=x²-2ax+3 在 [1,3] 的最小值 | a<1：4-2a；1≤a≤3：3-a²；a>3：12-6a | `c4_03_quadratic_minimum.json` | 0 |
| 4.4 | x²-2ax+a+2=0 有两个不等实根 | a∈(-∞,-1)∪(2,+∞) | `c4_04_discriminant_range.json` | 0 |
| 4.5 | ax²-(a+1)x+1<0 | a<0：x<1/a 或 x>1；a=0：x>1；0<a<1：1<x<1/a；a=1：∅；a>1：1/a<x<1 | `c4_05_quadratic_parameter_factor.json` | 0 |

### 五、易错与异常输入

| # | 题目 | 答案 | 文件 | 门 |
| --- | --- | --- | --- | --- |
| 5.1 | √(x²)=3 | x=±3 | `c5_01_sqrt_square.json` | 0 |
| 5.2 | 1/(x-1)=2/(x²-1) | 无解（空集） | `c5_02_extraneous_root.json` | 0 |
| 5.3 | a²=4，b²=9，求 a+b | {-5,-1,1,5} | `c5_03_square_conditions.json` | 0 |
| 5.4 | 若 x²>4，则 x>2 | 不成立；反例 x=-3 | `c5_04_implication_counterexample.json` | 0 |
| 5.5 | sin α=1/2，α∈[0,2π] | α=π/6 或 5π/6 | `c5_05_trig_equation.json` | 0 |

## 本次覆盖的关键点

- **增根与排除值**：1.4 只保留 x=4；1.5 舍去 x=2；5.2 唯一候选 x=1 是增根，最终无解。
- **分类完备性**：4.1 单独处理 k=0；4.2 比较 a 与 2；4.3 比较对称轴与区间；4.5 分出 a<0、a=0、0<a<1、a=1、a>1 五类。
- **负号与多解**：3.3 由 q²=4 得到 q=±2，两个 S₅ 都保留；5.1 与 5.5 都要求写出两个解；5.3 枚举四种符号组合。
- **命题真假**：5.4 用一个反例否定命题，并区分原命题与逆命题。
- **端点与严格性**：2.5 的左端点 -5 可取、右端点 -2 排除；4.2、4.5 都使用开端点；4.4 的边界 a=-1、2 对应 Δ=0，必须排除。

## 复现

在 `math-solver/` 目录：

```bash
for f in example/mvp-2026-10-18-expanded/*.json; do
  python3 scripts/validate_output.py validate --card "$f" --strict
done
```

数学核验（需要 sympy）：

```bash
python3 example/mvp-2026-10-18-expanded/verify_math.py
```

Windows 上若 `python3` 是应用商店占位程序，请换成实际解释器路径。

## 边界说明

- 25 道题都是本次测试的实际输出，不是随机抽样或大规模基准。
- `verify_math.py` 用 SymPy 求根、判别式、区间和有限点抽样；它检查的是这些题的具体答案与关键分支，不构成对任意高中题的准确率保证。
- 结构门不验数学；数学正确性仍需宿主或人复核。
