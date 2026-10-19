#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立核验 rsi/splits 中四份题的数学事实与标准答案。

核验方式：
- 方程/不等式：SymPy 求解、定义域过滤、代回；
- 参数不等式：按参数符号分类求解；
- 概率/数列/三角/几何：公式与数值/符号对照；
- 证明题：因式分解 + 枚举 + 数值验证；
- 歧义题：构造两个满足条件但答案不同的例子；
- 标准答案规格：value_set / interval_set / piecewise / empty_set 与计算结果对照，
  text_forms 与一份参考正确解答对照。

它不验证模型输出，也不替代人工复核；它只确认“题目 + 标准答案”自洽。

退出码：0 = 全部通过；1 = 有失败；2 = 输入/依赖错误。
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

SPLITS = Path(__file__).resolve().parents[1]
REPO = SPLITS.parents[1]
sys.path.insert(0, str(SPLITS))
sys.path.insert(0, str(REPO / "math-solver" / "bench"))

import sympy as sp  # noqa: E402

from engine.answers import norm_light  # noqa: E402
import build_splits  # noqa: E402

TRUTHS = {
    name: {case["case_id"]: item for case, item in pairs}
    for name, pairs in build_splits.SPLITS.items()
}
CASES = {
    name: {case["case_id"]: case for case, _ in pairs}
    for name, pairs in build_splits.SPLITS.items()
}

X = sp.symbols("x", real=True)
CHECKS: list[dict] = []
REFERENCE_ANSWERS = {
    "SEL-02": "a_{10}=29",
    "SEL-03": "c=√39",
    "SEL-04": "4/7",
    "SEL-07": "最大值10，最小值1",
    "SEL-08": "α=π/6 或 α=5π/6",
    "SEL-09": "α=π/4 或 α=5π/4",
    "SEL-14": "2<m<3",
    "SEL-15": "m∈(-√5,√5)",
    "SEL-16": "sinαcosα=-3/8，sin³α+cos³α=11/16",
    "SEL-17": "3/4",
    "SEL-18": "a_{10}=91",
    "SEL-19": "a≤1",
    "SEL-20": "R=1",
    "SEAL-05": "α=π/4 或 α=7π/4",
    "OOD-01": "n³-n 能被 6 整除",
    "OOD-02": "(a+b+c)(1/a+1/b+1/c)≥9",
    "OOD-03": "余弦值为 √2/2",
    "OOD-04": "末两位为 01",
    "PROBE-02": "6√2",
}


def check(case_id: str, ok: bool, detail: str) -> None:
    CHECKS.append({"case_id": case_id, "ok": bool(ok), "detail": detail})


def rational_set(values) -> set:
    return {sp.Rational(str(value)) for value in values}


def roots_of(expr):
    return [sp.simplify(root) for root in sp.solve(expr, X)
            if root.is_real is not False]


def valid_roots(expr, predicate):
    return [root for root in roots_of(expr) if predicate(root)]


def interval_tuple(interval):
    return (
        float(interval.start) if interval.start != -sp.oo else float("-inf"),
        float(interval.end) if interval.end != sp.oo else float("inf"),
        not interval.left_open,
        not interval.right_open,
    )


def union_intervals(solution):
    if isinstance(solution, sp.Union):
        parts = solution.args
    else:
        parts = (solution,)
    return sorted(interval_tuple(part) for part in parts)


def check_value_spec(case_id, truth, computed, detail=""):
    spec = truth["answer_check"]
    if spec["kind"] != "value_set":
        return
    expected = rational_set(spec["values"])
    check(case_id, expected == set(computed),
          f"value_set {sorted(map(str, expected))} vs {sorted(map(str, computed))} {detail}")


def check_text_spec(case_id, truth):
    spec = truth["answer_check"]
    if spec["kind"] != "text_forms":
        return
    reference = norm_light(REFERENCE_ANSWERS.get(case_id, ""))
    missing = [group for group in spec["groups"]
               if not any(norm_light(option) in reference for option in group)]
    check(case_id, not missing and bool(reference),
          f"text_forms missing={missing} reference={REFERENCE_ANSWERS.get(case_id)}")


def check_piecewise_spec(case_id, truth, expected_labels):
    spec = truth["answer_check"]
    if spec["kind"] != "piecewise":
        return
    labels = [case["label"] for case in spec["cases"]]
    check(case_id, set(labels) == set(expected_labels),
          f"piecewise labels {labels} vs {expected_labels}")


def check_interval_spec(case_id, truth, solution):
    spec = truth["answer_check"]
    if spec["kind"] != "interval_set":
        return
    expected = sorted(
        (float("-inf") if item["lo"] is None else float(item["lo"]),
         float("inf") if item["hi"] is None else float(item["hi"]),
         bool(item["lo_closed"]), bool(item["hi_closed"]))
        for item in spec["intervals"])
    check(case_id, expected == union_intervals(solution),
          f"interval spec {expected} vs solution {union_intervals(solution)}")


# ---------------------------------------------------------------------------
# selection
# ---------------------------------------------------------------------------

def verify_selection():
    # SEL-01
    roots = roots_of(sp.Eq(2 * (3 * X - 1), 5 * X + 4))
    check("SEL-01", roots == [6], f"roots={roots}")
    check_value_spec("SEL-01", TRUTHS["selection"]["SEL-01"],
                     [sp.Integer(6)])

    # SEL-02
    a1, d = sp.symbols("a1 d", real=True)
    sol = sp.solve([sp.Eq(a1 + d, 5), sp.Eq(a1 + 4 * d, 14)], [a1, d], dict=True)
    a10 = sp.simplify(sol[0][a1] + 9 * sol[0][d]) if sol else None
    check("SEL-02", a10 == 29, f"a1,d={sol}, a10={a10}")
    check_text_spec("SEL-02", TRUTHS["selection"]["SEL-02"])

    # SEL-03
    c_sq = 5**2 + 7**2 - 2 * 5 * 7 * sp.cos(sp.pi / 3)
    check("SEL-03", sp.simplify(sp.sqrt(c_sq) - sp.sqrt(39)) == 0,
          f"c^2={c_sq}, c={sp.sqrt(c_sq)}")
    check_text_spec("SEL-03", TRUTHS["selection"]["SEL-03"])

    # SEL-04
    probability = sp.binomial(4, 1) * sp.binomial(3, 1) / sp.binomial(7, 2)
    check("SEL-04", sp.simplify(probability - sp.Rational(4, 7)) == 0,
          f"P={probability}")
    check_text_spec("SEL-04", TRUTHS["selection"]["SEL-04"])

    # SEL-05
    valid = valid_roots(sp.Eq(sp.sqrt(3 * X + 1), X - 1),
                        lambda r: r >= 1 and sp.simplify(
                            sp.sqrt(3 * r + 1) - (r - 1)) == 0)
    check("SEL-05", valid == [5], f"valid roots={valid}")
    check_value_spec("SEL-05", TRUTHS["selection"]["SEL-05"],
                     [sp.Integer(5)])

    # SEL-06
    kpos = sp.Symbol("k", positive=True)
    kneg = sp.Symbol("k", negative=True)
    sol_pos = sp.solve_univariate_inequality(kpos * X - 3 < 0, X, relational=False)
    sol_zero = sp.S.Reals  # k=0 时 -3<0 恒成立
    sol_neg = sp.solve_univariate_inequality(kneg * X - 3 < 0, X, relational=False)
    ok = (sol_pos == sp.Interval.open(-sp.oo, 3 / kpos)
          and sol_zero == sp.S.Reals
          and sol_neg == sp.Interval.open(3 / kneg, sp.oo))
    check("SEL-06", ok, f"k>0:{sol_pos} k=0:{sol_zero} k<0:{sol_neg}")
    check_piecewise_spec("SEL-06", TRUTHS["selection"]["SEL-06"],
                         ["k>0", "k=0", "k<0"])

    # SEL-07
    f = X**2 - 4 * X + 5
    values = {"f(-1)": sp.Integer(10), "f(2)": sp.Integer(1), "f(3)": sp.Integer(2)}
    check("SEL-07", values == {"f(-1)": f.subs(X, -1), "f(2)": f.subs(X, 2),
                               "f(3)": f.subs(X, 3)},
          f"values={values}")
    check_text_spec("SEL-07", TRUTHS["selection"]["SEL-07"])

    # SEL-08
    trig = sp.solveset(sp.Eq(sp.sin(X), sp.Rational(1, 2)), X,
                       domain=sp.Interval(0, 2 * sp.pi))
    expected_trig = sp.FiniteSet(sp.pi / 6, 5 * sp.pi / 6)
    check("SEL-08", trig == expected_trig, f"trig={trig}")
    check_text_spec("SEL-08", TRUTHS["selection"]["SEL-08"])

    # SEL-09
    trig = sp.solveset(sp.Eq(sp.tan(X), 1), X,
                       domain=sp.Interval.open(0, 2 * sp.pi))
    expected_trig = sp.FiniteSet(sp.pi / 4, 5 * sp.pi / 4)
    check("SEL-09", trig == expected_trig, f"trig={trig}")
    check_text_spec("SEL-09", TRUTHS["selection"]["SEL-09"])

    # SEL-12: two triangles with sides 3,5 but different included angles.
    c60 = sp.sqrt(3**2 + 5**2 - 2 * 3 * 5 * sp.cos(sp.pi / 3))
    c90 = sp.sqrt(3**2 + 5**2)
    check("SEL-12", sp.simplify(c60 - c90) != 0,
          f"third side varies: {c60} vs {c90}")

    # Boundary cases: expected route/clarify and required phrases.
    for case_id, action in (("SEL-10", "route"), ("SEL-11", "route"),
                            ("SEL-12", "clarify"), ("SEL-13", "clarify")):
        case = CASES["selection"][case_id]
        check(case_id, case["expected_action"] == action,
              f"expected_action={case['expected_action']}")

    # SEL-14：两根都大于 1 的参数二次方程
    m = sp.symbols("m", real=True)
    delta = 4 * m**2 - 4 * (m + 2)
    cond_delta = sp.solve_univariate_inequality(delta > 0, m, relational=False)
    cond_sum = sp.solve_univariate_inequality(2 * m > 2, m, relational=False)
    cond_f1 = sp.solve_univariate_inequality(3 - m > 0, m, relational=False)
    intersection = cond_delta.intersect(cond_sum).intersect(cond_f1)
    check("SEL-14", intersection == sp.Interval.open(2, 3),
          f"conditions -> {intersection}")
    check_text_spec("SEL-14", TRUTHS["selection"]["SEL-14"])

    # SEL-15：椭圆与直线联立
    poly = sp.expand(X**2 / 4 + (X + m)**2 - 1)
    disc = sp.discriminant(poly, X)
    cond = sp.solve_univariate_inequality(disc > 0, m, relational=False)
    expected_cond = sp.Interval.open(-sp.sqrt(5), sp.sqrt(5))
    check("SEL-15", sp.simplify(disc - (5 - m**2)) == 0 and cond == expected_cond,
          f"disc={disc}, condition={cond}")
    check_text_spec("SEL-15", TRUTHS["selection"]["SEL-15"])

    # SEL-16：sin+cos 与立方和
    sin_cos = (sp.Rational(1, 2)**2 - 1) / 2
    sum_cubes = sp.Rational(1, 2) * (1 - sin_cos)
    check("SEL-16", sin_cos == sp.Rational(-3, 8)
          and sum_cubes == sp.Rational(11, 16),
          f"sin*cos={sin_cos}, sum cubes={sum_cubes}")
    check_text_spec("SEL-16", TRUTHS["selection"]["SEL-16"])

    # SEL-17：条件概率
    p_a, p_b = sp.Rational(6, 10), sp.Rational(5, 10)
    conditional = p_a / (1 - (1 - p_a) * (1 - p_b))
    check("SEL-17", conditional == sp.Rational(3, 4),
          f"P(A|A∪B)={conditional}")
    check_text_spec("SEL-17", TRUTHS["selection"]["SEL-17"])

    # SEL-18：递推求和
    a10 = 1 + 2 * sum(range(1, 10))
    check("SEL-18", a10 == 91, f"a10={a10}")
    check_text_spec("SEL-18", TRUTHS["selection"]["SEL-18"])

    # SEL-19：f'(x)>=0 在 [1,2] 恒成立
    sample_ok = all(3 * x**2 - 3 * 1 >= 0
                    for x in (sp.Integer(1), sp.Rational(3, 2), sp.Integer(2)))
    boundary_fail = 3 * 1**2 - 3 * sp.Rational(11, 10) < 0
    check("SEL-19", sample_ok and boundary_fail,
          f"a=1 ok={sample_ok}, a=1.1 fail={boundary_fail}")
    check_text_spec("SEL-19", TRUTHS["selection"]["SEL-19"])

    # SEL-20：正弦定理求外接圆半径
    radius = sp.sqrt(3) / (2 * sp.sin(sp.pi / 3))
    check("SEL-20", sp.simplify(radius - 1) == 0, f"R={radius}")
    check_text_spec("SEL-20", TRUTHS["selection"]["SEL-20"])


# ---------------------------------------------------------------------------
# sealed
# ---------------------------------------------------------------------------

def verify_sealed():
    # SEAL-01
    roots = roots_of(sp.Eq(5 * (X - 3), 2 * X + 6))
    check("SEAL-01", roots == [7], f"roots={roots}")
    check_value_spec("SEAL-01", TRUTHS["sealed_id"]["SEAL-01"],
                     [sp.Integer(7)])

    # SEAL-02
    value = 3 * 2**5
    check("SEAL-02", value == 96, f"a6={value}")
    check_value_spec("SEAL-02", TRUTHS["sealed_id"]["SEAL-02"],
                     [sp.Integer(96)])

    # SEAL-03
    valid = valid_roots(sp.Eq(sp.sqrt(2 * X + 3), X),
                        lambda r: r >= 0 and sp.simplify(
                            sp.sqrt(2 * r + 3) - r) == 0)
    check("SEAL-03", valid == [3], f"valid roots={valid}")
    check_value_spec("SEAL-03", TRUTHS["sealed_id"]["SEAL-03"],
                     [sp.Integer(3)])

    # SEAL-04
    apos = sp.Symbol("a", positive=True)
    aneg = sp.Symbol("a", negative=True)
    sol_pos = sp.solve_univariate_inequality(apos * X - 2 > 0, X, relational=False)
    sol_zero = sp.EmptySet  # a=0 时 -2>0 不成立
    sol_neg = sp.solve_univariate_inequality(aneg * X - 2 > 0, X, relational=False)
    ok = (sol_pos == sp.Interval.open(2 / apos, sp.oo)
          and sol_zero == sp.EmptySet
          and sol_neg == sp.Interval.open(-sp.oo, 2 / aneg))
    check("SEAL-04", ok, f"a>0:{sol_pos} a=0:{sol_zero} a<0:{sol_neg}")
    check_piecewise_spec("SEAL-04", TRUTHS["sealed_id"]["SEAL-04"],
                         ["a>0", "a=0", "a<0"])

    # SEAL-05
    trig = sp.solveset(sp.Eq(sp.cos(X), sp.sqrt(2) / 2), X,
                       domain=sp.Interval(0, 2 * sp.pi))
    expected_trig = sp.FiniteSet(sp.pi / 4, 7 * sp.pi / 4)
    check("SEAL-05", trig == expected_trig, f"trig={trig}")
    check_text_spec("SEAL-05", TRUTHS["sealed_id"]["SEAL-05"])


# ---------------------------------------------------------------------------
# OOD
# ---------------------------------------------------------------------------

def verify_ood():
    # OOD-01
    n = sp.Symbol("n", integer=True)
    factored = sp.factor(n**3 - n)
    check("OOD-01", sp.simplify(factored - n * (n - 1) * (n + 1)) == 0,
          f"factor={factored}")
    divisible = all(((value**3 - value) % 6 == 0) for value in range(-30, 31))
    check("OOD-01", divisible, "n in [-30,30] all divisible by 6")
    check_text_spec("OOD-01", TRUTHS["ood"]["OOD-01"])

    # OOD-02
    a, b, c = sp.symbols("a b c", positive=True)
    expanded = sp.expand((a + b + c) * (1 / a + 1 / b + 1 / c))
    expected = 3 + a / b + b / a + a / c + c / a + b / c + c / b
    check("OOD-02", sp.simplify(expanded - expected) == 0,
          f"expanded={expanded}")
    random.seed(7)
    numeric_ok = True
    for _ in range(20):
        vals = [sp.Rational(random.randint(1, 20), random.randint(1, 20))
                for _ in range(3)]
        expr = (vals[0] + vals[1] + vals[2]) * (
            1 / vals[0] + 1 / vals[1] + 1 / vals[2])
        numeric_ok = numeric_ok and bool(sp.simplify(expr) >= 9)
    check("OOD-02", numeric_ok, "20 random positive triples satisfy >= 9")
    check_text_spec("OOD-02", TRUTHS["ood"]["OOD-02"])

    # OOD-03
    v = sp.Matrix([1, 0, -1])
    normal = sp.Matrix([0, 0, 1])
    sin_theta = abs(v.dot(normal)) / (v.norm() * normal.norm())
    cos_theta = sp.sqrt(1 - sin_theta**2)
    check("OOD-03", sp.simplify(cos_theta - sp.sqrt(2) / 2) == 0,
          f"cos={cos_theta}")
    check_text_spec("OOD-03", TRUTHS["ood"]["OOD-03"])

    # OOD-04
    mod = pow(3, 100, 100)
    check("OOD-04", mod == 1, f"3^100 mod 100 = {mod}")
    check("OOD-04", sp.totient(100) == 40 and pow(3, 20, 100) == 1,
          "phi(100)=40 and 3^20=1 mod 100")
    check_text_spec("OOD-04", TRUTHS["ood"]["OOD-04"])


# ---------------------------------------------------------------------------
# probes
# ---------------------------------------------------------------------------

def verify_probes():
    # PROBE-01
    roots = roots_of(sp.Eq(7 * X - 5, 4 * X + 10))
    check("PROBE-01", roots == [5], f"roots={roots}")
    check_value_spec("PROBE-01", TRUTHS["probes"]["PROBE-01"],
                     [sp.Integer(5)])

    # PROBE-02
    simplified = sp.simplify(sp.sqrt(50) + sp.sqrt(18) - sp.sqrt(8))
    check("PROBE-02", sp.simplify(simplified - 6 * sp.sqrt(2)) == 0,
          f"simplified={simplified}")
    check_text_spec("PROBE-02", TRUTHS["probes"]["PROBE-02"])

    # PROBE-03: perimeter 20, different areas.
    rectangles = [(2, 8), (3, 7)]
    check("PROBE-03", all(2 * (l + w) == 20 for l, w in rectangles)
          and len({l * w for l, w in rectangles}) == 2,
          f"areas={[l * w for l, w in rectangles]}")

    # PROBE-04: a1=2, different d -> different S10.
    s10 = lambda d: sp.Rational(10, 2) * (2 * 2 + 9 * d)
    check("PROBE-04", s10(1) != s10(2), f"S10(d=1)={s10(1)}, S10(d=2)={s10(2)}")

    # PROBE-05
    roots = roots_of(sp.Eq(1 / (X - 1), 1 / (X - 2)))
    check("PROBE-05", roots == [], f"roots={roots}")
    check("PROBE-05",
          TRUTHS["probes"]["PROBE-05"]["answer_check"]["kind"]
          == "empty_set", "answer spec is empty_set")

    # PROBE-06
    real_roots = [root for root in sp.solve(sp.Eq(sp.sqrt(X + 1), -2), X)
                  if root.is_real is not False]
    check("PROBE-06", real_roots == [], f"real roots={real_roots}")

    # PROBE-07
    roots = roots_of(sp.Eq(X / (X - 3), 3 / (X - 3)))
    valid = [root for root in roots if sp.simplify(root - 3) != 0]
    check("PROBE-07", valid == [], f"roots={roots}, valid={valid}")

    # PROBE-08
    solution = sp.solve_univariate_inequality(sp.sqrt(2 * X - 1) < X,
                                              X, relational=False)
    expected = sorted([
        (0.5, 1.0, True, False),
        (1.0, float("inf"), False, False),
    ])
    check("PROBE-08", union_intervals(solution) == expected,
          f"solution={solution}")


def verify_specs():
    """检查每份 truth 的 must_include / 必填字段。"""
    for name, pairs in build_splits.SPLITS.items():
        for case, item in pairs:
            case_id = case["case_id"]
            check(case_id, item["case_id"] == case_id, "case/truth ids match")
            if case["expected_action"] in ("route", "clarify"):
                check(case_id, bool(item["must_include"]),
                      "route/clarify has must_include")
            if case["expected_action"] == "route":
                check(case_id,
                      item["answer_check"].get("route_to") == case["expected_route"],
                      "route_to matches case.expected_route")


def main() -> int:
    try:
        verify_selection()
        verify_sealed()
        verify_ood()
        verify_probes()
        verify_specs()
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                         ensure_ascii=False, indent=2))
        return 2

    failed = [item for item in CHECKS if not item["ok"]]
    payload = {
        "ok": not failed,
        "check_count": len(CHECKS),
        "failed_count": len(failed),
        "failed": failed,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
