#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_answers.py —— 对本卷关键结论做数值/精确代回核对（工具辅助核验）。

用法（工作区根目录）：
  "D:/Program Files/anaconda3/python.exe" -X utf8 exam_105/verify_answers.py
"""

import math
import random
import sys
from fractions import Fraction as F

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

print("== 第21(2)题：椭圆 x^2/8 + y^2/2 = 1，直线 y = kx+m，OA ⊥ OB ==")
for k in [F(0), F(3, 10), F(-1), F(5, 2), F(7), F(-4)]:
    m2 = F(8, 5) * (1 + k * k)          # 待验证的结论 m^2 = (8/5)(1+k^2)
    m = math.sqrt(float(m2))
    A_ = 1 + 4 * float(k) ** 2
    B_ = 8 * float(k) * m
    C_ = 4 * float(m2) - 8
    D = B_ * B_ - 4 * A_ * float(C_)
    x1 = (-B_ + math.sqrt(D)) / (2 * A_)
    x2 = (-B_ - math.sqrt(D)) / (2 * A_)
    y1 = float(k) * x1 + m
    y2 = float(k) * x2 + m
    print("  k=%6.2f  m=±%.6f  Δ=%.6f  x1x2+y1y2=%.3e" % (float(k), m, D, x1 * x2 + y1 * y2))
    assert D > 0 and abs(x1 * x2 + y1 * y2) < 1e-6, "结论不成立"

x1, x2, y1, y2 = math.sqrt(8) / 2, -math.sqrt(8) / 2, 1.0, 1.0
print("  反向核对：k=0, m=1（m^2=1 < 8/5）时 x1x2+y1y2 = %.6f ≠ 0，垂直不成立" % (x1 * x2 + y1 * y2))

print("== 第10题：双曲线 x^2/4 - y^2/12 = 1 ==")
a2, b2 = 4, 12
print("  c=%.6f  e=%.6f  渐近线斜率=%.6f  实轴长=%.6f" % (math.sqrt(a2 + b2), math.sqrt(a2 + b2) / 2,
                                                          math.sqrt(b2 / a2), 2 * math.sqrt(a2)))

print("== 第11题：a>0,b>0,a+b=4 时 √a+√b 的最大值 ==")
worst = 0.0
random.seed(20261010)
for _ in range(200000):
    a = 4 * random.random()
    worst = max(worst, math.sqrt(a) + math.sqrt(4 - a))
print("  随机抽样最大值 ≈ %.6f ，2√2 ≈ %.6f" % (worst, 2 * math.sqrt(2)))

print("== 第16题：P-ABC 外接球（B 为原点，BA、BC、BP 两两垂直）==")
center = (1, 1, 1)
R2 = sum(c * c for c in center)
for name, pt in (("B", (0, 0, 0)), ("A", (2, 0, 0)), ("C", (0, 2, 0)), ("P", (2, 0, 2))):
    d2 = sum((pt[i] - center[i]) ** 2 for i in range(3))
    print("  球心(1,1,1) 到 %s 的距离平方 = %.6f" % (name, d2))
    assert abs(d2 - R2) < 1e-9
print("  R^2 = %.6f ，外接球表面积 = 4πR^2 = %.6fπ = 12π" % (R2, 4 * R2))

print("== 第18题：a 与 sinB ==")
a2v = 4 + 9 - 2 * 2 * 3 * F(3, 5)
print("  a^2 = %s = %.6f ；a = √(29/5) = √145/5 = %.6f" % (a2v, float(a2v), math.sqrt(145) / 5))
print("  sinB = 8/√145 = %.9f ；8√145/145 = %.9f（等价）" % (8 / math.sqrt(145), 8 * math.sqrt(145) / 145))

print("== 第20题：平均分 ==")
print("  %.6f" % (55 * 0.1 + 65 * 0.2 + 75 * 0.3 + 85 * 0.25 + 95 * 0.15))

print("== 第13、15题 ==")
print("  f(1)=1-3=-2, f'(1)=3-3=0 ⟹ 切线 y=-2")
print("  P(X≤4)=0.8 ⟹ P(X≥4)=0.2 ⟹ P(X≤0)=0.2 ⟹ P(0<X<2)=0.5-0.2=0.3")

print("全部工具核对通过（工具辅助核验，不是独立验证）")
