"""核验新例的指定计算事实；不调用模型、不进行诊断行为评分。"""
from fractions import Fraction
from pathlib import Path
import json

checks = []


def check(name, condition, scope):
    if not condition:
        raise AssertionError(name)
    checks.append({"name": name, "passed": True, "scope": scope})


def multiply_linear(a, b):
    # 降幂系数：(a0*x+a1)(b0*x+b1)。
    return (a[0]*b[0], a[0]*b[1]+a[1]*b[0], a[1]*b[1])


check("N01 分式方程", multiply_linear((1, -1), (1, 1)) == (1, 0, -1)
      and 2-1 == 1 and 1-1 == 0,
      "验证因式分解、唯一候选值及分母为零")
check("N02 根式反例", (-3)**2 == 9 and 3 != -3,
      "验证反例；一般恒等式 sqrt(x²)=|x| 由非负平方根定义说明")
check("N03 有效约分", multiply_linear((1, -2), (1, 2)) == (1, 0, -4)
      and all(Fraction(x*x-4, x-2) == x+2 for x in (-3, 0, 1, 3)),
      "系数展开及有限点计算；约分须保留 x≠2")
check("N04 参数不等式", all((a*x > 1) == (
      x > Fraction(1, a) if a > 0 else x < Fraction(1, a))
      for a in (-2, -1, 1, 2)
      for x in (Fraction(-2), Fraction(-1), Fraction(0), Fraction(1), Fraction(2)))
      and not (0 > 1),
      "有限样本及零参数检查；一般结论由不等式乘除规则说明")
check("N05 两根代回", multiply_linear((1, -3), (1, 3)) == (1, 0, -9)
      and all(x*x == 9 for x in (-3, 3)),
      "因式分解系数与两个候选根代回")
check("N08 取倒数反例", -2 < -1 and Fraction(1, -2) > Fraction(1, -1),
      "反例否定错误全称断言")
result = {"passed_groups": len(checks), "checks": checks,
          "limitation": "只核验列出的数学事实，不是自动模型评测，也不替代一般证明。"}
output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
Path(__file__).with_name("新例检验_计算证据.json").write_text(output)
print(output)
