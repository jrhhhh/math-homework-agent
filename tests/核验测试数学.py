#!/usr/bin/env python3
"""仅核验固定测试材料的计算事实，不是通用数学诊断器或模型行为评测。"""
from fractions import Fraction
import json
import math


def main():
    checks = []

    def check(name, condition, scope):
        if not condition:
            raise AssertionError(name)
        checks.append({"name": name, "passed": True, "scope": scope})

    check("T01 根式候选根", all(x*x-x-2 == 0 for x in (-1, 2))
          and math.sqrt(2+2) == 2 and math.sqrt(-1+2) != -1,
          "核验两个候选根及代回；二次方程完整性依赖因式分解推导")
    check("T02/T06 零因子", all(x*(x-1) == 0 for x in (0, 1)),
          "两个给定解满足方程；完整性由零乘积性质说明")
    samples = [Fraction(-10), Fraction(-7, 2), Fraction(-3), Fraction(-5, 2), Fraction(0)]
    check("T03 不等式样本及边界", all((-2*x > 6) == (x < -3) for x in samples),
          "有限点检查，不是不等式等价的完整证明")
    samples = [Fraction(0), Fraction(1), Fraction(3, 2), Fraction(2), Fraction(3)]
    check("T04 定义域样本及端点", all(
        (x-1 >= 0 and x-2 != 0) == (1 <= x < 2 or x > 2) for x in samples),
        "检查边界样本；完整定义域由两个条件的交集说明")
    # 多项式恒等采用系数比较，而不是通过样本外推。
    check("T05 配方法与根", (1, -6, 9-4) == (1, -6, 5)
          and all(x*x-6*x+5 == 0 for x in (1, 5)),
          "系数比较及两个候选根代回")
    check("T08 参数样本", all(a*Fraction(1, a) == 1 for a in (-3, -1, 1, 2))
          and 0 != 1, "有限非零参数样本；一般分支由除法条件说明")
    check("T09 错误参考答案", 2*2+1 == 5 and 2*3+1 != 5, "直接代回")
    check("T11 两个根和错误候选值", all((x-1)*(x-2) == 0 for x in (1, 2))
          and (-2-1)*(-2-2) != 0, "直接代回；完整性由零乘积性质说明")
    check("T12 正确终值与错误步骤", 2*(3-1) == 4 and (2, -2) != (2, -1)
          and Fraction(4+1, 2) != 3, "系数比较、局部移项和原方程代回")
    check("示例变式题", all(x*x-x-6 == 0 for x in (-2, 3))
          and math.sqrt(3+6) == 3 and math.sqrt(-2+6) != -2,
          "候选根与代回；仅用于参考示例中的变式题")
    print(json.dumps({"passed_groups": len(checks), "checks": checks,
                      "limitation": "未运行模型行为评测；不证明任意数学题的可靠性"},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
