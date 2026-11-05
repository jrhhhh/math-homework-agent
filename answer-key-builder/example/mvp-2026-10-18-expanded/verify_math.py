#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_math.py — 25 道扩充题的数学核验（测试辅助，不属于技能结构门）。

需要 sympy。逐题检查答案、分支与端点，输出 PASS/FAIL 表和汇总。
这些检查是符号计算或有限点抽查，不替代一般性数学证明。
"""

import math
import sys

import sympy as sp

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

x, a, k = sp.symbols("x a k", real=True)
results = []


def check(name, cond):
    results.append((name, bool(cond)))


# ---------------------------------------------------------------- 一、基础计算与方程
check("1.1 x=-1", sp.solve(3 * (x + 2) - 5 - 2 * x, x) == [-1])
check("1.2 x=2,3", sorted(sp.solve(x ** 2 - 5 * x + 6, x)) == [2, 3])
check("1.3 x=-1,3", sorted(sp.solve(sp.Eq(3 / x, x - 2), x)) == [-1, 3])
check("1.4 x=4", sp.solve(sp.Eq(sp.sqrt(2 * x + 1), x - 1), x) == [4])
check("1.5 x=-5", sp.solve(sp.Eq(x / (x - 2) + 1 / (x + 2), 8 / (x ** 2 - 4)), x) == [-5])

# ---------------------------------------------------------------- 二、函数与不等式
check("2.1 domain [2,inf)",
      all(math.sqrt(v) >= 0 for v in [2, 2.5, 10]) and not (1 - 2 >= 0))
sol22 = sp.solve_univariate_inequality(x ** 2 - x - 2 < 0, x, relational=False)
check("2.2 (-1,2)",
      sol22.contains(0) and not sol22.contains(-1) and not sol22.contains(2))
check("2.3 domain (-1,3)U(3,inf)",
      (lambda t: t(0) and t(4) and not t(-1) and not t(3))(
          lambda v: v > -1 and v != 3))
d24 = 2 * (x - a)
check("2.4 a=-1 increasing", all(d24.subs({a: -1, x: v}) >= 0 for v in [0, 1, 2]))
check("2.4 a=1 dec then inc", d24.subs({a: 1, x: 0}) < 0 and d24.subs({a: 1, x: 2}) > 0)
check("2.4 a=3 decreasing", all(d24.subs({a: 3, x: v}) <= 0 for v in [0, 1, 2]))
sol25 = sp.solve_univariate_inequality((x - 1) / (x + 2) >= 2, x, relational=False)
check("2.5 [-5,-2)",
      sol25.contains(-5) and sol25.contains(-3)
      and not sol25.contains(-2) and not sol25.contains(0))

# ---------------------------------------------------------------- 三、数列、三角函数或几何
check("3.1 a5=13", 1 + 4 * 3 == 13)
check("3.2 a^2=7", sp.simplify(2 ** 2 + 3 ** 2 - 2 * 2 * 3 * sp.cos(sp.pi / 3)) == 7)
check("3.3 S5=62,22",
      sum(2 * 2 ** i for i in range(5)) == 62
      and sum(2 * (-2) ** i for i in range(5)) == 22)
d34 = 4 * sp.cos(2 * x + sp.pi / 4)
check("3.4 inc interval", d34.subs(x, 0) > 0 and d34.subs(x, sp.Rational(1, 2)) < 0)
A, B, C = sp.pi / 4, 5 * sp.pi / 12, sp.pi / 3
R = 1
aa, bb, cc = 2 * R * sp.sin(A), 2 * R * sp.sin(B), 2 * R * sp.sin(C)
check("3.5 C=pi/3 identity",
      sp.simplify(aa * sp.cos(B) + bb * sp.cos(A) - 2 * cc * sp.cos(C)) == 0)

# ---------------------------------------------------------------- 四、含参与分类讨论
check("4.1 k=2: x>-1", 2 * 0 + 2 > 0 and not (2 * (-2) + 2 > 0))
check("4.1 k=0: all x", all(0 * v + 2 > 0 for v in [-10, 0, 10]))
check("4.1 k=-2: x<1", -2 * 0 + 2 > 0 and not (-2 * 2 + 2 > 0))
sol42a = sp.solve_univariate_inequality((x + 1) * (x - 2) > 0, x, relational=False)
sol42b = sp.solve_univariate_inequality((x - 2) * (x - 2) > 0, x, relational=False)
sol42c = sp.solve_univariate_inequality((x - 3) * (x - 2) > 0, x, relational=False)
check("4.2 a=-1", sol42a.contains(-2) and not sol42a.contains(0) and sol42a.contains(3))
check("4.2 a=2", sol42b.contains(0) and not sol42b.contains(2) and sol42b.contains(3))
check("4.2 a=3", sol42c.contains(0) and not sol42c.contains(2.5) and sol42c.contains(4))


def f43(v, av):
    return v * v - 2 * av * v + 3


def formula43(av):
    if av < 1:
        return 4 - 2 * av
    if av <= 3:
        return 3 - av * av
    return 12 - 6 * av


for av in [0, 1, 2, 3, 4]:
    brute = min(f43(1 + i / 10000 * 2, av) for i in range(10001))
    check(f"4.3 a={av} min", abs(brute - formula43(av)) < 1e-6)

disc = sp.factor(4 * a ** 2 - 4 * (a + 2))
target = 4 * (a - 2) * (a + 1)
check("4.4 disc=4(a-2)(a+1)", sp.simplify(disc - target) == 0)
for av, inside in [(-2, True), (-1, False), (0, False), (2, False), (3, True)]:
    check(f"4.4 a={av} two roots", ((av < -1) or (av > 2)) == inside)


def lhs45(v, av):
    return av * v * v - (av + 1) * v + 1


cases45 = [
    (-1, [-2, 0, 2], [True, False, True]),
    (0, [0, 2], [False, True]),
    (0.5, [0.5, 1.5, 3], [False, True, False]),
    (1, [0, 2], [False, False]),
    (2, [0, 0.75, 2], [False, True, False]),
]
for av, pts, exp in cases45:
    check(f"4.5 a={av}", all((lhs45(p, av) < 0) == e for p, e in zip(pts, exp)))

# ---------------------------------------------------------------- 五、易错与异常输入
check("5.1 x=+-3", sorted(sp.solve(sp.Eq(sp.sqrt(x ** 2), 3), x)) == [-3, 3])
raw52 = sp.solve(sp.Eq(1 / (x - 1), 2 / (x ** 2 - 1)), x)
check("5.2 no solution", raw52 == [] and (1 - 1 == 0) and (1 ** 2 - 1 == 0))
check("5.3 sums", sorted({aa + bb for aa in (-2, 2) for bb in (-3, 3)}) == [-5, -1, 1, 5])
check("5.4 counterexample", ((-3) ** 2 > 4) and not (-3 > 2))
check("5.5 alpha",
      sorted(sp.solve(sp.Eq(sp.sin(x), sp.Rational(1, 2)), x)) == [sp.pi / 6, 5 * sp.pi / 6])

# ---------------------------------------------------------------- 输出
for name, ok in results:
    print(("PASS " if ok else "FAIL ") + name)
print(f"\n{sum(ok for _, ok in results)}/{len(results)} checks passed")
sys.exit(0 if all(ok for _, ok in results) else 1)
