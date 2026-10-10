#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_card.py —— 按 cases_105.json 的真实内容算指纹，生成 card_105.json。

为什么不手写指纹：evidence 里的 12 位指纹必须与「题面 + 学生过程」逐字对应，
手写必然对不上（E_EVIDENCE_STALE）。算法与同伴 scripts/handoff_check.py 的
version() 逐字相同，也与 error-atlas/example/build_cards.py 一致。

用法（工作区根目录）：
  "D:/Program Files/anaconda3/python.exe" exam_105/build_card.py
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
CASES = BASE / "cases_105.json"
CARD = BASE / "card_105.json"


def fingerprint(case):
    """与同伴 handoff_check.py 的 version() 逐字相同，取前 12 位十六进制。"""
    data = {"grade_level": case["grade_level"], "problem": case["problem"],
            "student_solution": case["student_solution"]}
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def ref(case):
    return "[%s#%s]" % (case["id"], fingerprint(case))


def main():
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    by_id = {c["id"]: c for c in cases}
    t10, t11 = ref(by_id["T10"]), ref(by_id["T11"])
    t21, t22 = ref(by_id["T21"]), ref(by_id["T22"])

    patterns = [
        {
            "pattern": "分支穷尽不足",
            "cause_type": "分支/边界遗漏",
            "evidence": (
                t10 + " 与 " + t11 + " 都是同伴诊断为分支/边界遗漏的题："
                "T10 的四条陈述里 C 成立却未被选中（渐近线 y = ±√3 x），"
                "T11 的四条不等式里 D 成立却未被选中（√a + √b ≤ 2√2）；"
                "两题都是把一组并列结论交上去、没有逐条判完。"
            ),
            "case_count": 2,
            "capability_hypothesis": "逻辑完备性",
            "countermeasure": (
                "遇到「下列说法正确的有」这类题，先在草稿上给 A/B/C/D 各留一行，"
                "逐条写「成立」或「不成立」并写出依据，四个都落笔后再把勾选行抄成答案。"
            ),
        },
        {
            "pattern": "过程规范松动",
            "cause_type": "论证缺口",
            "evidence": (
                t21 + " 与 " + t22 + " 都是同伴判定为论证缺口的题："
                "T21 已经把 OA⊥OB 译成 x1x2 + y1y2 = 0、也写出了韦达定理，"
                "却没有合并出 5m^2 - 8 - 8k^2 = 0、更没有给出 m 的范围；"
                "T22 只算出驻点 x = e^(a-1)，没有把 f' 的符号讨论写成单调区间。"
                "两题的推导链都停在「最后一步落地」之前。"
            ),
            "case_count": 2,
            "capability_hypothesis": "步骤留痕与记录",
            "countermeasure": (
                "把「条件译成式子」与「从式子解出结论」分成两行写："
                "写完韦达定理或求导那一步，紧接一行就补「所以……」，这一步不许留在心里。"
            ),
        },
        {
            "pattern": "结果自检缺位",
            "cause_type": "论证缺口",
            "evidence": (
                t22 + " 与 " + t21 + " 都是论证缺口："
                "T22 定出 x = e^(a-1) 后没有回代核验它两侧 f' 的符号，单调区间就没有落地；"
                "T21 列完韦达定理后没有核验判别式 Δ > 0 这个前提，也没有把结果代回椭圆；"
                "两题都在「验一下再交」这一步停住。"
            ),
            "case_count": 2,
            "capability_hypothesis": "自我验证",
            "countermeasure": (
                "每写下一个关键结论，立刻回头做一次核对：判别式符号、驻点两侧的符号、"
                "解出的参数代回原式，各查一遍并把核对结果写在结论旁边。"
            ),
        },
    ]

    commonality = (
        "第 " + t10 + " 题与第 " + t11 + " 题同属「分支穷尽不足」："
        "一组并列结论没有逐条判完就交了选项；"
        "第 " + t21 + " 题与第 " + t22 + " 题则同属「过程规范松动」与「结果自检缺位」："
        "条件都已经正确译成式子（韦达定理、求导驻点），"
        "但推导链的最后一步与交卷前的核对都被略去。"
        "四道题合起来是同一个方向：算得对，却把「走完最后一步」和「回头验一次」当成了可以省的事。"
    )

    card = {
        "error_patterns": patterns,
        "cross_case_commonality": commonality,
        "strength_kept": (
            "这批题里仍然成立的是「把条件翻译成代数式」这一步："
            "T21 第(1)问的离心率、b^2 与代入点 (2,1) 全对（a^2 = 8、b^2 = 2），"
            "第(2)问的联立方程 (1+4k^2)x^2 + 8kmx + 4m^2 - 8 = 0、韦达定理系数与 y1y2 的展开都正确；"
            "T22 的定义域 (0,+∞) 与求导 f'(x) = ln x + 1 - a 也正确；"
            "T10、T11 里已选中的选项经复核都真。"
        ),
        "capability_profile": (
            "这批题共同指向的假设是：**步骤留痕与记录**偏弱——条件能译成式子，"
            "但「从式子推到底、把结论写出来」这最后一步常被省略。"
            "样本目前只有四道题，属于初步判断，需再用新题验证。"
        ),
        "next_training_target": "步骤留痕与记录",
        "practice_authorized": False,
        "practice_items": [],
        "generation_basis": "",
    }

    CARD.write_text(json.dumps(card, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", CARD.name)
    for case in cases:
        print("fingerprint", case["id"], fingerprint(case))


if __name__ == "__main__":
    main()
