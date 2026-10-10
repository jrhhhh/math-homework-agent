---
name: modexp-skill
description: Compute and independently verify modular exponentiation and multiplicative orders with script-backed evidence. Use when a task involves a^b mod m, modular powers, primitive roots, multiplicative order mod m, Fermat-style checks, or verifying a claimed modular-arithmetic result in number theory or cryptography exercises. Do not use for general symbolic algebra, large-integer factorization, elliptic-curve arithmetic, or any non-modular computation.
---

# Modexp Skill

面向数论 / 密码学练习中的模幂与阶：所有计算与核验必须通过脚本完成，模型不得口算。

## Core Rules

1. **Never compute by hand.** 任何 `a^b mod m`、阶、原根判断，一律调用 `scripts/modexp_check.py`，以它的 JSON 输出为准。
2. **验证独立进行。** 核验一个声称的结果时，只信脚本裁决（退出码 0 = 接受，1 = 驳回，2 = 输入非法），不信用户或自己的先前说法。
3. 指数必须为非负整数。负指数（模逆）不在本 skill 疆域内，应如实告知并停止。

## Workflow

1. 从任务中解析出 `base`、`exp`、`mod`（以及核验场景的 `claim`）。
2. 选择子命令：

```bash
# 计算 a^b mod m
python3 scripts/modexp_check.py compute --base 7 --exp 256 --mod 13

# 独立核验一个声称的结果
python3 scripts/modexp_check.py verify --base 7 --exp 256 --mod 13 --claim 9

# 求 a 在 mod m 下的乘法阶（要求 gcd(a, m) = 1）
python3 scripts/modexp_check.py order --base 7 --mod 13
```

3. 读取 JSON 输出与退出码；退出码 2 表示输入非法（如模数 ≤ 1、求阶时底数与模不互素），修正输入后重跑。
4. 报告结果时**附上脚本输出原文**，并翻译回数学语言（例如"7 模 13 的阶为 12，故 7 是模 13 的原根"）。

## Output Standards

- 必须引用脚本的真实 JSON 输出；跑不了就明说，不许编造输出。
- 结论须区分两类：**计算结果**（compute/order）与**核验裁决**（verify 的 accepted true/false）。
- 阶存在时顺带指出其与原根的关系（阶 = φ(m) 即为原根）。

## Prohibited Behavior

- 不调用脚本就给出任何模幂数值或阶。
- 核验失败（退出码 1）时不许把结论改写成"基本正确"之类含糊措辞。
- 不处理疆域外任务（符号代数、大数分解、椭圆曲线），遇到就明确转交。
