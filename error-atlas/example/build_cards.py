#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_cards.py — 从 cases_junior.json 的真实内容算出指纹，生成四份示例卡。

为什么要用脚本生成而不是手写：`evidence` 里的 12 位指纹必须与题面/过程**逐字对应**，
手写一定会错。这个脚本让示例卡可复现：改了 cases 就重跑一次。

用法（在 error-atlas/ 目录下）：
  python build_cards.py
"""

import hashlib
import json
import pathlib
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = pathlib.Path(__file__).resolve().parent
CASES = BASE / "cases_junior.json"


def fingerprint(case):
    """与同伴 scripts/handoff_check.py 的 version() 逐字相同，取前 12 位。"""
    data = {"grade_level": case["grade_level"], "problem": case["problem"],
            "student_solution": case["student_solution"]}
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def ref(case):
    return "[%s#%s]" % (case["id"], fingerprint(case))


def main():
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    by_id = {c["id"]: c for c in cases}
    t1, t2, t3 = ref(by_id["T1"]), ref(by_id["T2"]), ref(by_id["T3"])
    t4, t5 = ref(by_id["T4"]), ref(by_id["T5"])
    t6 = ref(by_id["T6"])

    patterns = [
        {
            "pattern": "条件加工缺位",
            "cause_type": "条件失效",
            "evidence": t4 + " 与 " + t5 + " 都是同伴诊断为条件失效的题："
                              "T4 去分母时默认 x-1 不为零、没写出定义域 x≠1；"
                              "T5 把解集写成 x<2 的闭区间、边界 2 该不该取判错了。"
                              "两题都是「约束条件没先摆出来」就往下算。",
            "case_count": 2,
            "capability_hypothesis": "条件提取与转译",
            "countermeasure": "下次读题先把所有取值范围条件圈出来，再动笔变形；"
                              "遇到不等号先单独判定边界取不取，写在草稿第一行。"
        },
        {
            "pattern": "分支穷尽不足",
            "cause_type": "分支/边界遗漏",
            "evidence": t2 + " 与 " + t6 + " 都是同伴诊断为分支/边界遗漏的题："
                              "T2 在 Δ=4>0 时只给一个交点、三种情形没分开讨论；"
                              "T6 去绝对值只取了一支、漏掉 x-1=-2。"
                              "两题都是「有几种情形」没有先列全。",
            "case_count": 2,
            "capability_hypothesis": "逻辑完备性",
            "countermeasure": "遇到判别式、绝对值、参数范围这类问题，先在草稿上写下"
                              "「要分几种情形」，再逐种填结论。"
        },
        {
            "pattern": "过程规范松动",
            "cause_type": "运算错误",
            "evidence": t3 + " 同伴诊断为运算错误：移项时 +3 没有变号、写成 7+3；"
                              "同批题里 " + t1 + " 也把去分母的常数项 1 漏乘了。"
                              "两题都是「变形规则被压缩成一步」造成的。",
            "case_count": 2,
            "capability_hypothesis": "步骤留痕与记录",
            "countermeasure": "把每步只写一个变形，移项和去分母各占一行，"
                              "写完逐项标号核对一次再往下走。"
        },
    ]

    commonality = ("第 " + t1 + " 题的去分母漏乘常数项、第 " + t3 + " 题的移项没变号，"
                   "合起来是同一个「过程规范松动」：变形步骤被压缩、每一步没有逐项核对；"
                   "第 " + t4 + " 题的定义域约束没写出来、第 " + t5 + " 题的不等号边界判错，"
                   "则同属「条件加工缺位」这一类反复出现的条件漏检；"
                   "而第 " + t2 + " 题与第 " + t6 + " 题都栽在「分支穷尽不足」上——"
                   "有几种情形没有先列全就直接下结论。")

    base_card = {
        "error_patterns": patterns,
        "cross_case_commonality": commonality,
        "strength_kept": ("这六道题的最终计算都算对了：T1 的合并同类项、T2 的判别式求值、"
                          "T4 解出的 x=5/3、T5 解出的 x>2 都没有算错，"
                          "说明运算基本功是稳的，问题集中在变形前的条件处理与分支枚举。"),
        "capability_profile": ("这六道题共同指向的假设是：**步骤留痕与记录**偏弱——"
                               "为了快而把变形压成一步，导致漏乘与不变号。"
                               "样本量目前为六道题，属于初步判断，需再用新题验证。"),
        "next_training_target": "过程规范松动",
        "practice_authorized": False,
        "practice_items": [],
        "generation_basis": "",
    }

    practice_items = [
        {
            "id": "P1",
            "pattern_ref": 3,
            "difficulty": "同型巩固",
            "student_prompt": "解方程：2x+3=7。",
            "answer": "x=2",
            "solution_steps": "移项：2x=7-3=4；两边同除以 2：x=2。移项时 +3 变成 -3（变号）。",
            "source_pattern": "过程规范松动"
        },
        {
            "id": "P2",
            "pattern_ref": 3,
            "difficulty": "同型巩固",
            "student_prompt": "解方程：5-2x=1。",
            "answer": "x=2",
            "solution_steps": "移项：-2x=1-5=-4；两边同除以 -2：x=2。两次符号变化都要逐项核对。",
            "source_pattern": "过程规范松动"
        },
        {
            "id": "P3",
            "pattern_ref": 1,
            "difficulty": "变式迁移",
            "student_prompt": "若 x>0 且 2x+3=7，求 x 的值。",
            "answer": "x=2",
            "solution_steps": "先记下约束 x>0；解 2x+3=7 得 x=2，满足 x>0，故 x=2。",
            "source_pattern": "条件加工缺位"
        },
        {
            "id": "P4",
            "pattern_ref": 2,
            "difficulty": "变式迁移",
            "student_prompt": "已知二次函数 f(x)=x^2-4x+3，求它与 x 轴交点的个数。",
            "answer": "2 个",
            "solution_steps": "判别式 Δ=16-12=4>0，所以有两个不同实根，交点个数为 2。注意与 Δ=0、Δ<0 两种情形对照。",
            "source_pattern": "分支穷尽不足"
        },
        {
            "id": "P5",
            "pattern_ref": 2,
            "difficulty": "综合拔高",
            "student_prompt": "已知直线 y=x+1 与抛物线 y=x^2-6x+5，求它们的交点个数。",
            "answer": "2 个",
            "solution_steps": "令 x+1=x^2-6x+5，整理得 x^2-7x+4=0；判别式 Δ=49-16=33>0，所以有两个不同交点，交点个数为 2。",
            "source_pattern": "分支穷尽不足"
        },
    ]

    good = dict(base_card)
    good["practice_authorized"] = True
    good["practice_items"] = practice_items
    good["generation_basis"] = ("依据聚合维度 过程规范松动（第 T1、T3 题）与 条件加工缺位（第 T4 题）、"
                                "分支穷尽不足（第 T2 题）三类模式定制：5 题分别绑定这三个模式，"
                                "覆盖同型巩固、变式迁移、综合拔高三个难度档。")

    # 教具一：归因合格但出题不合格——模式 3 未被覆盖、P2 引用样本量不足的模式、
    # P3 的答案是 4（真值为 2）用来触发答案代回不成立。
    bad_practice_items = json.loads(json.dumps(practice_items, ensure_ascii=False))
    for item in bad_practice_items:
        if item["id"] == "P1":
            item["pattern_ref"] = 1
            item["source_pattern"] = "条件加工缺位"
        if item["id"] == "P2":
            item["pattern_ref"] = 1
            item["source_pattern"] = "条件加工缺位"
        if item["id"] == "P3":
            item["pattern_ref"] = 2
            item["source_pattern"] = "分支穷尽不足"
            item["answer"] = "x=5"
        if item["id"] == "P5":
            item["pattern_ref"] = 2
            item["source_pattern"] = "分支穷尽不足"
    bad_practice = dict(base_card)
    bad_practice["practice_authorized"] = True
    bad_practice["practice_items"] = bad_practice_items
    bad_practice["generation_basis"] = "依据聚合维度 条件加工缺位（第 T4 题）与 分支穷尽不足（第 T2 题）定制。"
    # 让最后两道题挤在同一档，触发 E_DIFFICULTY_UNKNOWN（三档必须都出现）
    for item in bad_practice["practice_items"]:
        if item["id"] in ("P3", "P4", "P5"):
            item["difficulty"] = "变式迁移"

    # 教具二：证据不足——case_count=1、引用不存在的 T9、指纹过期、使用了被否定的核验方式。
    thin_cases = json.loads(CASES.read_text(encoding="utf-8"))
    thin_cases[0]["cause"]["method"] = "numeric_only"
    thin = dict(base_card)
    thin_patterns = json.loads(json.dumps(patterns, ensure_ascii=False))
    thin_patterns[0]["case_count"] = 1
    thin_patterns[1]["evidence"] = "[T9#001122334455] 引用了一道没有交上来的题。"
    thin_patterns[2]["evidence"] = "[T3#000000000000] 指纹与当前题面不符。"
    thin["error_patterns"] = thin_patterns
    thin["capability_profile"] = ("这批题呈现的假设是：**步骤留痕与记录**偏弱，"
                                  "属于初步判断，需再用新题验证。")

    # 教具三：归因合格但越界——自产错因 + 否定同伴 + 稳定判定 + 单题判错 +
    # 夹带题目 + 排复习计划 + 评分 + 置信度 + 语气对人。
    bad_card = json.loads(json.dumps(good, ensure_ascii=False))
    bad_card["error_patterns"][0]["countermeasure"] = \
        "你之所以错是因为审题太快，根本原因是习惯问题；每天做 5 道，一周就能补上。"
    bad_card["error_patterns"][1]["countermeasure"] = \
        "其实不是分类问题，你就是不会分情形，得分一直上不去，置信度不高。"
    bad_card["error_patterns"][2]["countermeasure"] = \
        "你太粗心了。下面这道题你试试：解 3x-1=5。"
    bad_card["capability_profile"] = \
        "你长期能力不足：步骤留痕与记录一直很弱，初步判断已可确认。"

    outputs = {
        "junior_three_cases.json": base_card,
        "practice_with_answers.json": good,
        "bad_thin_card.json": thin,
        "bad_card.json": bad_card,
        "bad_practice_card.json": bad_practice,
        "cases_junior_thin.json": thin_cases,
    }
    for name, payload in outputs.items():
        path = BASE / name
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
        print("wrote", name)
    print("fingerprints:", {c["id"]: fingerprint(c) for c in cases})


if __name__ == "__main__":
    main()
