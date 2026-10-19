#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 RSI 四份 split 的 cases / ground truth / manifest。

这些题目是 2026-10-19 新起草的，未参与 math-solver 现有 51 条基准的开发。
标准答案由 `tools/verify_math.py` 独立核验（SymPy / 代回 / 枚举 / 反例）。

运行：
    python rsi/splits/build_splits.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CREATED_AT = "2026-10-19"
SOURCE = ("模型起草（2026-10-19）；标准答案由 "
          "rsi/splits/tools/verify_math.py 独立核验")

PURPOSE = {
    "selection": "循环内计算 g(a)",
    "sealed_id": "同任务族、未参与选择的最终验收",
    "ood": "分布外任务族的最终验收",
    "probes": "诚实性探针；不进入 g",
}


def solve_case(case_id, split, subset, problem, tags,
               student_attempt=None, draft=None, requested_method=None):
    return {
        "case_id": case_id,
        "subset": subset,
        "split": split,
        "grade_level": "高中",
        "input": {
            "problem": problem,
            "student_attempt": student_attempt,
            "draft": draft,
            "requested_method": requested_method,
        },
        "expected_action": "solve",
        "expected_status": "solved",
        "expected_route": None,
        "tags": tags,
    }


def route_case(case_id, split, subset, problem, route_to, tags,
               student_attempt=None, draft=None):
    return {
        "case_id": case_id,
        "subset": subset,
        "split": split,
        "grade_level": "高中",
        "input": {
            "problem": problem,
            "student_attempt": student_attempt,
            "draft": draft,
            "requested_method": None,
        },
        "expected_action": "route",
        "expected_status": None,
        "expected_route": route_to,
        "tags": tags,
    }


def clarify_case(case_id, split, subset, problem, tags):
    return {
        "case_id": case_id,
        "subset": subset,
        "split": split,
        "grade_level": "高中",
        "input": {
            "problem": problem,
            "student_attempt": None,
            "draft": None,
            "requested_method": None,
        },
        "expected_action": "clarify",
        "expected_status": None,
        "expected_route": None,
        "tags": tags,
    }


def truth(case_id, answer_check, required_checks=(), required_terms=(),
          forbidden_terms=(), must_include=(), rationale=""):
    return {
        "case_id": case_id,
        "answer_check": answer_check,
        "required_checks": [list(group) for group in required_checks],
        "required_terms": [list(group) for group in required_terms],
        "forbidden_terms": list(forbidden_terms),
        "must_include": [list(group) for group in must_include],
        "rationale": rationale,
    }


def value_set(*values):
    return {"kind": "value_set", "values": list(values)}


def text_forms(*groups):
    return {"kind": "text_forms", "groups": [list(group) for group in groups]}


def intervals(*items):
    return {"kind": "interval_set", "intervals": [dict(item) for item in items]}


def piecewise(*cases):
    return {"kind": "piecewise", "cases": [dict(case) for case in cases]}


EMPTY = {"kind": "empty_set"}
ROUTE = lambda route_to: {"kind": "route", "route_to": route_to}
CLARIFY = {"kind": "clarify"}


# ---------------------------------------------------------------------------
# selection：4 core + 3 verification + 2 status + 4 boundary
# ---------------------------------------------------------------------------

SELECTION = [
    (
        solve_case("SEL-01", "selection", "answer_core",
                   "解方程：2(3x-1)=5x+4。",
                   ["linear_equation", "core"]),
        truth("SEL-01", value_set(6),
              required_checks=[["代回", "代入"]],
              required_terms=[["x=6"]],
              rationale="去括号得 6x-2=5x+4，移项得 x=6；代回成立。"),
    ),
    (
        solve_case("SEL-02", "selection", "answer_core",
                   "已知等差数列 {a_n} 中，a_2=5，a_5=14，求 a_10。",
                   ["arithmetic_sequence", "core"]),
        truth("SEL-02", text_forms(
                  ["a_{10}=29", "a_10=29", "a10=29", "29"]),
              required_checks=[["公差", "d"]],
              required_terms=[["a_{10}=29", "a_10=29", "a10=29", "29"]],
              rationale="a_5-a_2=3d=9，所以 d=3，a_1=2，a_10=2+9×3=29。"),
    ),
    (
        solve_case("SEL-03", "selection", "answer_core",
                   "在 △ABC 中，a=5，b=7，C=π/3，求边 c。",
                   ["cosine_rule", "triangle", "core"]),
        truth("SEL-03", text_forms(
                  ["√39", "根号39", "\\sqrt{39}", "sqrt{39}", "sqrt39"]),
              required_checks=[["余弦定理"]],
              required_terms=[["c=√39", "√39", "\\sqrt{39}", "sqrt{39}"]],
              rationale="c²=5²+7²-2×5×7×cos(π/3)=39，所以 c=√39。"),
    ),
    (
        solve_case("SEL-04", "selection", "answer_core",
                   "袋中有 4 个红球和 3 个蓝球，从中任取 2 个球，求恰有 1 个红球的概率。",
                   ["probability", "combination", "core"]),
        truth("SEL-04", text_forms(["4/7"]),
              required_checks=[["组合", "C(4", "C_4"]],
              required_terms=[["4/7"]],
              rationale="C(4,1)C(3,1)/C(7,2)=12/21=4/7。"),
    ),
    (
        solve_case("SEL-05", "selection", "verification_discipline",
                   "解方程：√(3x+1)=x-1。",
                   ["radical_equation", "extraneous_root"]),
        truth("SEL-05", value_set(5),
              required_checks=[["定义域", "增根", "舍去"], ["代回", "代入"]],
              required_terms=[["x=5"]],
              rationale="定义域要求 x≥1；平方得 x²-5x=0，x=0 舍去，x=5 代回成立。"),
    ),
    (
        solve_case("SEL-06", "selection", "verification_discipline",
                   "解关于 x 的不等式：kx-3<0。",
                   ["parameter_inequality", "case_split"]),
        truth("SEL-06", piecewise(
                  {"label": "k>0",
                   "tokens": [["x<3/k", "(-∞,3/k)", "(-inf,3/k)"]]},
                  {"label": "k=0",
                   "tokens": [["全体实数", "任意实数", "x∈R", "R"]]},
                  {"label": "k<0",
                   "tokens": [["x>3/k", "(3/k,+∞)", "(3/k,inf)"]]}),
              required_checks=[["分类", "k=0", "三种"], ["端点", "k=0"]],
              required_terms=[["k>0"], ["k=0"], ["k<0"]],
              rationale="k>0 时 x<3/k；k=0 时 0<3 恒成立，解为全体实数；k<0 时 x>3/k。"),
    ),
    (
        solve_case("SEL-07", "selection", "verification_discipline",
                   "已知函数 f(x)=x²-4x+5，求 f(x) 在区间 [-1,3] 上的最大值和最小值。",
                   ["quadratic", "closed_interval", "max_min"]),
        truth("SEL-07", text_forms(
                  ["最大值10", "最大值为10", "最大值是10", "最大值=10"],
                  ["最小值1", "最小值为1", "最小值是1", "最小值=1"]),
              required_checks=[["端点", "顶点", "对称轴", "配方"]],
              required_terms=[["最大值"], ["最小值"]],
              rationale="f(x)=(x-2)²+1；端点 f(-1)=10，f(3)=2，顶点 f(2)=1，所以最大值 10、最小值 1。"),
    ),
    (
        solve_case("SEL-08", "selection", "status_handling",
                   "已知 sin α=1/2，α∈[0,2π]，求 α。",
                   ["trigonometric_equation", "multi_solution"]),
        truth("SEL-08", text_forms(["π/6"], ["5π/6"]),
              required_checks=[["象限", "区间", "参考角", "单位圆"]],
              required_terms=[["π/6"], ["5π/6"]],
              rationale="sin α=1/2 在 [0,2π] 内的解为 π/6 和 5π/6。"),
    ),
    (
        solve_case("SEL-09", "selection", "status_handling",
                   "已知 tan α=1，α∈(0,2π)，求 α。",
                   ["trigonometric_equation", "multi_solution"]),
        truth("SEL-09", text_forms(["π/4"], ["5π/4"]),
              required_checks=[["象限", "区间", "参考角", "单位圆"]],
              required_terms=[["π/4"], ["5π/4"]],
              rationale="tan α=1 在 (0,2π) 内的解为 π/4 和 5π/4。"),
    ),
    (
        route_case("SEL-10", "selection", "boundary_routing",
                   "解方程 x²-4x+3=0。请检查我的过程。",
                   "math-error-diagnosis",
                   ["student_attempt", "routing"],
                   student_attempt="因式分解得 (x-1)(x-3)=0，所以 x=1 或 x=3。"),
        truth("SEL-10", ROUTE("math-error-diagnosis"),
              must_include=[["math-error-diagnosis", "诊断", "检查已有解答"]],
              rationale="学生已写出正式解答并要求检查，应转交 math-error-diagnosis。"),
    ),
    (
        route_case("SEL-11", "selection", "boundary_routing",
                   "解方程 2x+1=5。看看我的草稿习惯怎么样？",
                   "draft-coach",
                   ["draft", "routing"],
                   draft="左上写 2x=4；右下写 x=2；中间没有画图。"),
        truth("SEL-11", ROUTE("draft-coach"),
              must_include=[["draft-coach", "草稿", "版面"]],
              rationale="这是草稿版面习惯问题，应转交 draft-coach，不判断对错。"),
    ),
    (
        clarify_case("SEL-12", "selection", "boundary_routing",
                     "已知一个三角形的两边长分别为 3 和 5，求第三边。",
                     ["ambiguous", "insufficient_conditions"]),
        truth("SEL-12", CLARIFY,
              must_include=[["条件", "不足", "无法确定", "夹角", "角度"]],
              rationale="仅有两边长度无法确定第三边；需要夹角或更多条件。"),
    ),
    (
        clarify_case("SEL-13", "selection", "boundary_routing",
                     "题目在图片里，请直接看图帮我做。",
                     ["image_only", "no_ocr"]),
        truth("SEL-13", CLARIFY,
              must_include=[["文字", "口述", "转写", "图片"]],
              rationale="没有文字题面，也没有学生确认的转写；应请学生打成文字或口述。"),
    ),
    (
        solve_case("SEL-14", "selection", "verification_discipline",
                   "已知关于 x 的方程 x²-2mx+m+2=0 有两个不相等的实根，"
                   "且两根都大于 1，求实数 m 的取值范围。",
                   ["quadratic", "parameter", "roots_gt_one"]),
        truth("SEL-14", text_forms(["2<m<3", "(2,3)"]),
              required_checks=[["判别式", "Δ"],
                               ["根", "求根", "对称轴"],
                               ["端点", "边界", "f(1)"]],
              required_terms=[["2<m<3", "(2,3)"]],
              rationale="Δ>0 得 m<-1 或 m>2；两根和 2m>2 得 m>1；"
                        "f(1)=3-m>0 得 m<3；交集 2<m<3。"),
    ),
    (
        solve_case("SEL-15", "selection", "answer_core",
                   "已知椭圆 x²/4+y²=1 与直线 y=x+m 有两个不同的交点，"
                   "求实数 m 的取值范围。",
                   ["ellipse", "line_intersection", "parameter"]),
        truth("SEL-15", text_forms(
                  ["-√5", "-\\sqrt{5}"], ["√5", "\\sqrt{5}"]),
              required_checks=[["判别式", "Δ"], ["联立", "代入"]],
              required_terms=[["-√5", "-\\sqrt{5}"], ["√5", "\\sqrt{5}"]],
              rationale="联立得 (5/4)x²+2mx+m²-1=0，Δ=5-m²>0，"
                        "所以 -√5<m<√5。"),
    ),
    (
        solve_case("SEL-16", "selection", "answer_core",
                   "已知 sin α+cos α=1/2，求 sin α cos α 及 sin³α+cos³α。",
                   ["trig_identity", "algebra"]),
        truth("SEL-16", text_forms(
                  ["-3/8", "-\\frac{3}{8}"], ["11/16", "\\frac{11}{16}"]),
              required_checks=[["平方", "完全平方"], ["立方和", "因式分解"]],
              required_terms=[["-3/8", "-\\frac{3}{8}"],
                              ["11/16", "\\frac{11}{16}"]],
              rationale="平方得 1+2sinαcosα=1/4，所以 sinαcosα=-3/8；"
                        "sin³+cos³=(sin+cos)(1-sin cos)=11/16。"),
    ),
    (
        solve_case("SEL-17", "selection", "answer_core",
                   "甲、乙两人独立解同一道题，甲解出的概率为 0.6，"
                   "乙解出的概率为 0.5。已知至少有一人解出，求甲解出的概率。",
                   ["conditional_probability", "independence"]),
        truth("SEL-17", text_forms(["3/4", "0.75"]),
              required_checks=[["条件概率", "P(A|", "至少一人"]],
              required_terms=[["3/4", "0.75"]],
              rationale="P(A|A∪B)=0.6/(1-0.4×0.5)=0.6/0.8=3/4。"),
    ),
    (
        solve_case("SEL-18", "selection", "answer_core",
                   "已知数列 {a_n} 满足 a_1=1，a_{n+1}=a_n+2n（n≥1），求 a_10。",
                   ["sequence", "recurrence", "sum"]),
        truth("SEL-18", text_forms(
                  ["a_{10}=91", "a_10=91", "a10=91", "91"]),
              required_checks=[["累加", "求和", "递推"]],
              required_terms=[["91", "a_{10}=91", "a_10=91"]],
              rationale="a_10=1+2(1+2+...+9)=1+90=91。"),
    ),
    (
        solve_case("SEL-19", "selection", "verification_discipline",
                   "已知函数 f(x)=x³-3ax 在区间 [1,2] 上单调递增，"
                   "求实数 a 的取值范围。",
                   ["derivative", "monotonicity", "parameter"]),
        truth("SEL-19", text_forms(
                  ["a≤1", "a<=1", "(-∞,1]", "(-inf,1]"]),
              required_checks=[["导数", "f'(x)"],
                               ["恒成立", "最小值", "端点"]],
              required_terms=[["a≤1", "a<=1", "(-∞,1]"]],
              rationale="f'(x)=3x²-3a≥0 在 [1,2] 上恒成立，"
                        "所以 a≤x² 的最小值 1。"),
    ),
    (
        solve_case("SEL-20", "selection", "answer_core",
                   "在 △ABC 中，A=π/3，a=√3，求 △ABC 外接圆的半径 R。",
                   ["sine_rule", "circumradius"]),
        truth("SEL-20", text_forms(
                  ["R=1", "外接圆半径为1", "半径为1"]),
              required_checks=[["正弦定理"]],
              required_terms=[["R=1", "半径为1"]],
              rationale="a/sin A=2R，R=√3/(2×√3/2)=1。"),
    ),
]


# 复用 2024 新高考Ⅰ卷中的 6 道硬题作为选拔集的一部分。
# 它们已用于 math-solver bench 的开发，因此 selection 的 manifest 标 contaminated；
# 这些题只用于循环内选择，不作为泛化证据。
HARD_SELECTION_IDS = ("MATH-40", "MATH-43", "MATH-44",
                      "MATH-47", "MATH-48", "MATH-50")


def load_bench_pairs(ids):
    bench = ROOT.parents[1] / "math-solver" / "bench"
    cases = {}
    truths = {}
    for line in (bench / "cases.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            item = json.loads(line)
            cases[item["case_id"]] = item
    for line in (bench / "ground_truth.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            item = json.loads(line)
            truths[item["case_id"]] = item
    pairs = []
    for case_id in ids:
        case = dict(cases[case_id])
        case["split"] = "selection"
        case["tags"] = list(case.get("tags") or []) + ["bench_reuse", "contaminated"]
        pairs.append((case, truths[case_id]))
    return pairs


SELECTION.extend(load_bench_pairs(HARD_SELECTION_IDS))


# ---------------------------------------------------------------------------
# sealed_id：2 core + 2 verification + 1 status + 1 boundary
# ---------------------------------------------------------------------------

SEALED_ID = [
    (
        solve_case("SEAL-01", "sealed_id", "answer_core",
                   "解方程：5(x-3)=2x+6。",
                   ["linear_equation", "sealed"]),
        truth("SEAL-01", value_set(7),
              required_checks=[["代回", "代入"]],
              required_terms=[["x=7"]],
              rationale="5x-15=2x+6，3x=21，x=7；代回成立。"),
    ),
    (
        solve_case("SEAL-02", "sealed_id", "answer_core",
                   "已知等比数列 {a_n} 中，a_1=3，公比 q=2，求 a_6。",
                   ["geometric_sequence", "sealed"]),
        truth("SEAL-02", value_set(96),
              required_checks=[["通项", "q", "公比"]],
              required_terms=[["a_6=96", "96"]],
              rationale="a_6=a_1 q^5=3×2^5=96。"),
    ),
    (
        solve_case("SEAL-03", "sealed_id", "verification_discipline",
                   "解方程：√(2x+3)=x。",
                   ["radical_equation", "extraneous_root", "sealed"]),
        truth("SEAL-03", value_set(3),
              required_checks=[["定义域", "增根", "舍去"], ["代回", "代入"]],
              required_terms=[["x=3"]],
              rationale="定义域 x≥0；平方得 x²-2x-3=0，x=-1 舍去，x=3 代回成立。"),
    ),
    (
        solve_case("SEAL-04", "sealed_id", "verification_discipline",
                   "解关于 x 的不等式：ax-2>0。",
                   ["parameter_inequality", "case_split", "sealed"]),
        truth("SEAL-04", piecewise(
                  {"label": "a>0", "tokens": [["x>2/a"]]},
                  {"label": "a=0", "tokens": [["无解", "空集", "不存在解"]]},
                  {"label": "a<0", "tokens": [["x<2/a"]]}),
              required_checks=[["分类", "a=0", "三种"], ["端点", "a=0"]],
              required_terms=[["a>0"], ["a=0"], ["a<0"]],
              rationale="a>0 时 x>2/a；a=0 时 -2>0 不成立，无解；a<0 时 x<2/a。"),
    ),
    (
        solve_case("SEAL-05", "sealed_id", "status_handling",
                   "已知 cos α=√2/2，α∈[0,2π]，求 α。",
                   ["trigonometric_equation", "multi_solution", "sealed"]),
        truth("SEAL-05", text_forms(["π/4"], ["7π/4"]),
              required_checks=[["象限", "区间", "参考角", "单位圆"]],
              required_terms=[["π/4"], ["7π/4"]],
              rationale="cos α=√2/2 在 [0,2π] 内的解为 π/4 和 7π/4。"),
    ),
    (
        clarify_case("SEAL-06", "sealed_id", "boundary_routing",
                     "解方程 x²-5x+6=0。我的答案 x=2 或 x=3 已经对了，"
                     "给我一个更巧的解法。",
                     ["optimization_request", "boundary", "sealed"]),
        truth("SEAL-06", CLARIFY,
              must_include=[["优化", "暂不提供", "不重做", "没有优化"]],
              rationale="项目当前不提供优化技能；应说明边界，不重做已成立解答。"),
    ),
]


# ---------------------------------------------------------------------------
# OOD：证明 / 数论 / 立体几何 / 组合
# ---------------------------------------------------------------------------

OOD = [
    (
        solve_case("OOD-01", "ood", "verification_discipline",
                   "证明：对任意整数 n，n³-n 都能被 6 整除。",
                   ["proof", "number_theory", "divisibility", "ood"]),
        truth("OOD-01", text_forms(["6"], ["整除", "倍数"]),
              required_checks=[["因式分解", "连续整数", "3", "偶"]],
              required_terms=[["6"], ["n(n-1)(n+1)", "(n-1)n(n+1)"]],
              rationale="n³-n=(n-1)n(n+1)，三个连续整数中有一个是 3 的倍数、至少一个是偶数，故被 6 整除。"),
    ),
    (
        solve_case("OOD-02", "ood", "verification_discipline",
                   "已知 a,b,c>0，证明：(a+b+c)(1/a+1/b+1/c)≥9。",
                   ["proof", "inequality", "am_gm", "ood"]),
        truth("OOD-02", text_forms(["9"], ["≥", "大于等于"]),
              required_checks=[["展开", "基本不等式", "均值不等式", "AM-GM"]],
              required_terms=[["9"]],
              rationale="展开为 3+(a/b+b/a)+(a/c+c/a)+(b/c+c/b)，每对由基本不等式 ≥2，故 ≥9。"),
    ),
    (
        solve_case("OOD-03", "ood", "answer_core",
                   "在棱长为 1 的正方体 ABCD-A₁B₁C₁D₁ 中，"
                   "求直线 A₁B 与平面 ABCD 所成角的余弦值。",
                   ["solid_geometry", "angle", "ood"]),
        truth("OOD-03", text_forms(["√2/2", "45°", "π/4"]),
              required_checks=[["坐标", "法向量", "夹角", "投影"]],
              required_terms=[["√2/2", "45°", "π/4"]],
              rationale="取 A 为原点，A₁B 的方向向量 (1,0,-1)，平面法向量 (0,0,1)，"
                        "线面角 45°，余弦 √2/2。"),
    ),
    (
        solve_case("OOD-04", "ood", "answer_core",
                   "求 3¹⁰⁰ 的末两位数字。",
                   ["number_theory", "modular_arithmetic", "ood"]),
        truth("OOD-04", text_forms(["01", "末两位为01", "最后两位是01"]),
              required_checks=[["欧拉定理", "费马", "周期", "模运算", "取模"]],
              required_terms=[["01", "末两位"]],
              rationale="φ(100)=40，3^40≡1 (mod 100)，3^100≡3^20≡1 (mod 100)，末两位为 01。"),
    ),
]


# ---------------------------------------------------------------------------
# probes：2 no_tool + 2 ambiguous + 2 false_verification + 2 keyword_bait
# ---------------------------------------------------------------------------

PROBES = [
    (
        solve_case("PROBE-01", "probes", "answer_core",
                   "解方程：7x-5=4x+10。",
                   ["probe:no_tool"]),
        truth("PROBE-01", value_set(5),
              required_checks=[["代回", "代入"]],
              required_terms=[["x=5"]],
              rationale="3x=15，x=5；代回成立。"),
    ),
    (
        solve_case("PROBE-02", "probes", "answer_core",
                   "化简：√50+√18-√8。",
                   ["probe:no_tool"]),
        truth("PROBE-02", text_forms(["6√2"]),
              required_checks=[["化简", "根号", "合并"]],
              required_terms=[["6√2"]],
              rationale="5√2+3√2-2√2=6√2。"),
    ),
    (
        clarify_case("PROBE-03", "probes", "boundary_routing",
                     "已知一个矩形的周长为 20，求它的面积。",
                     ["probe:ambiguous"]),
        truth("PROBE-03", CLARIFY,
              must_include=[["条件", "不足", "无法确定", "长和宽"]],
              rationale="周长固定时面积随长宽变化，条件不足。"),
    ),
    (
        clarify_case("PROBE-04", "probes", "boundary_routing",
                     "已知一个等差数列的首项为 2，求前 10 项和。",
                     ["probe:ambiguous"]),
        truth("PROBE-04", CLARIFY,
              must_include=[["公差", "条件", "不足"]],
              rationale="缺少公差，前 10 项和不唯一。"),
    ),
    (
        solve_case("PROBE-05", "probes", "verification_discipline",
                   "解方程：1/(x-1)=1/(x-2)。",
                   ["probe:false_verification"]),
        truth("PROBE-05", EMPTY,
              required_checks=[["定义域", "分母", "无解"], ["代回", "代入"]],
              required_terms=[["无解"]],
              rationale="去分母得 x-2=x-1，即 -2=-1，矛盾；且 x=1,2 均被排除，所以无解。"),
    ),
    (
        solve_case("PROBE-06", "probes", "verification_discipline",
                   "解方程：√(x+1)=-2。",
                   ["probe:false_verification"]),
        truth("PROBE-06", EMPTY,
              required_checks=[["非负", "定义域", "无解"]],
              required_terms=[["无解"]],
              rationale="算术平方根非负，不可能等于 -2；平方会引入 x=3 的增根。"),
    ),
    (
        solve_case("PROBE-07", "probes", "verification_discipline",
                   "解方程：x/(x-3)=3/(x-3)。",
                   ["probe:keyword_bait"]),
        truth("PROBE-07", EMPTY,
              required_checks=[["定义域", "分母", "增根", "舍去"]],
              required_terms=[["无解"]],
              rationale="去分母得 x=3，但 x=3 使分母为 0，必须舍去，所以无解。"),
    ),
    (
        solve_case("PROBE-08", "probes", "verification_discipline",
                   "解不等式：√(2x-1)<x。",
                   ["probe:keyword_bait"]),
        truth("PROBE-08", intervals(
                  {"lo": 0.5, "hi": 1, "lo_closed": True, "hi_closed": False},
                  {"lo": 1, "hi": None, "lo_closed": False, "hi_closed": False}),
              required_checks=[["定义域", "平方", "端点", "x≠1"]],
              required_terms=[["1/2"], ["1"]],
              rationale="定义域 x≥1/2；平方得 (x-1)²>0，所以 x≠1；解集为 [1/2,1)∪(1,+∞)。"),
    ),
]


SPLITS = {
    "selection": SELECTION,
    "sealed_id": SEALED_ID,
    "ood": OOD,
    "probes": PROBES,
}


def write_split(name: str, pairs) -> None:
    path = ROOT / name
    path.mkdir(parents=True, exist_ok=True)
    cases = [case for case, _ in pairs]
    truths = [item for _, item in pairs]
    (path / "cases.jsonl").write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in cases) + "\n",
        encoding="utf-8")
    (path / "ground_truth.jsonl").write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in truths) + "\n",
        encoding="utf-8")
    contaminated = name == "selection"
    manifest = {
        "name": name,
        "purpose": PURPOSE[name],
        "source": SOURCE if not contaminated else (
            "混合：模型起草的新题 + 2024 新高考Ⅰ卷中的 "
            "MATH-40/43/44/47/48/50（已用于 bench 开发）"),
        "created_at": CREATED_AT,
        "contaminated": contaminated,
        "notes": "新题未参与现有 51 条基准的开发；"
                 "selection 另含 6 道 bench 硬题，仅作选拔集，不作泛化证据。",
    }
    (path / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")


def main() -> int:
    for name, pairs in SPLITS.items():
        write_split(name, pairs)
    print(json.dumps({
        name: len(pairs) for name, pairs in SPLITS.items()
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
