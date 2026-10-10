#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_all_gates.py — 判据覆盖核验：确认每个码都真的能被打出来。

README 里说"每一条码背后都有一次真实触发"，这个脚本就是那句话的证据。
它分两部分：

  1. example/ 里的真实示例卡（可由 build_cards.py 重新生成）；
  2. 内存里临时构造的畸形卡（不该塞进 example/，但必须证明判据不是死代码）。

跑完打印三张门各自命中的码清单，以及**从未命中**的码（应为空）。

用法（在 error-atlas/ 目录下）：
  python verify_all_gates.py
"""

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import error_card_check as gates  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = pathlib.Path(__file__).resolve().parent
EX = BASE / "example"

VALIDATE_CODES = ("E_FIELDS", "E_COUNT", "E_ITEM_FIELDS", "E_PATTERN_UNKNOWN",
                  "E_CAUSE_TYPE_UNKNOWN", "E_CASE_COUNT_THIN", "E_PATTERN_EVIDENCE_THIN",
                  "E_GAP_UNKNOWN", "W_GAP_MISMATCH", "E_PATTERN_DUP", "E_EVIDENCE_FORM",
                  "E_COMMONALITY_NO_IDS", "E_PROFILE_UNKNOWN", "E_PROFILE_MULTI",
                  "W_TENTATIVE", "E_TARGET_UNKNOWN", "W_TARGET_MULTI", "W_SHORT", "W_TEMPLATE")
AUDIT_CODES = ("E_TOO_FEW_CASES", "E_EVIDENCE_NO_CASE", "E_EVIDENCE_STALE",
               "E_EVIDENCE_UNSUPPORTED", "E_CASE_COUNT_MISMATCH", "E_CAUSE_MISSING",
               "E_CAUSE_UNVERIFIED", "E_CAUSE_UNRESOLVED", "E_CAUSE_TYPE_MISMATCH",
               "W_COMMONALITY_WEAK", "W_ALL_SAME_CAUSE", "A_NEW_CAUSE", "A_OVERRIDE",
               "A_SINGLE_CASE_CAUSE", "A_STABLE_JUDGMENT", "A_SOLVE", "A_VARIANT",
               "A_PLAN", "A_SCORE", "A_CONFIDENCE", "A_PROBE", "W_LANGUAGE")
PRACTICE_CODES = ("E_PRACTICE_UNAUTHORIZED", "E_PRACTICE_MISSING", "W_NO_GENERATION_BASIS",
                  "E_PRACTICE_COUNT", "E_PRACTICE_ITEM_FIELDS", "E_PATTERN_REF_RANGE",
                  "E_PATTERN_REF_THIN", "E_PATTERN_UNCOVERED", "E_SOURCE_MISMATCH",
                  "E_DIFFICULTY_UNKNOWN", "E_PRACTICE_DUP", "E_ANSWER_MISSING",
                  "E_ANSWER_IN_PROMPT", "E_ANSWER_UNRELATED", "E_ANSWER_LINEAR_UNSAT",
                  "E_ANSWER_DOMAIN_VIOLATION", "W_NO_SOLUTION_BASIS", "W_ANSWER_NUMERIC_ONLY")

hits = {"validate": set(), "audit": set(), "practice": set()}


class FakeArgs:
    def __init__(self, **kw):
        self.strict = False
        self.verify_answers = False
        self.__dict__.update(kw)


def run(action, card, cases=None, **kw):
    """直接用模块里的 cmd_* 逻辑，但捕获它的 sys.exit。"""
    argv, tmp = sys.argv, None
    try:
        if cases is not None:
            tmp = BASE / "_tmp_cases.json"
            tmp.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
        card_path = BASE / "_tmp_card.json"
        card_path.write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
        args = FakeArgs(card=str(card_path))
        if cases is not None:
            args.cases = str(tmp)
        args.__dict__.update(kw)
        cmd = {"validate": gates.cmd_validate, "audit": gates.cmd_audit,
               "practice": gates.cmd_practice}[action]
        sys.argv = ["x"]
        try:
            cmd(args)
        except SystemExit:
            pass
    finally:
        sys.argv = argv


def collect(action, card, cases=None, **kw):
    """跑一次门，把 stdout 的 JSON 解析回来收集 code。"""
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        run(action, card, cases, **kw)
    payload = json.loads(buf.getvalue())
    for bucket in ("errors", "warnings"):
        for entry in payload.get(bucket, []):
            hits[action].add(entry["code"])
    for entry in payload.get("answer_verification", {}).get("problems", []):
        if entry.get("code"):
            hits[action].add(entry["code"])
    return payload


def run_gates(action, card, cases=None, **kw):
    """供外部探针复用：跑一次门并返回解析后的 JSON。"""
    return collect(action, card, cases, **kw)


def main():
    base = json.loads((EX / "junior_three_cases.json").read_text(encoding="utf-8"))
    cases = json.loads((EX / "cases_junior.json").read_text(encoding="utf-8"))
    good = json.loads((EX / "practice_with_answers.json").read_text(encoding="utf-8"))
    bad = json.loads((EX / "bad_card.json").read_text(encoding="utf-8"))
    thin = json.loads((EX / "bad_thin_card.json").read_text(encoding="utf-8"))
    thin_cases = json.loads((EX / "cases_junior_thin.json").read_text(encoding="utf-8"))
    bad_practice = json.loads((EX / "bad_practice_card.json").read_text(encoding="utf-8"))

    # ---- 真实示例卡
    collect("validate", base)
    collect("validate", bad)
    collect("validate", thin)
    collect("validate", bad_practice)
    collect("audit", base, cases)
    collect("audit", bad, cases)
    collect("audit", thin, thin_cases)
    collect("practice", base)
    collect("practice", good, verify_answers=True)
    collect("practice", bad_practice, verify_answers=True)

    # ---- 临时畸形卡（只活在核验过程里，不进 example/）
    def mutate(func):
        card = json.loads(json.dumps(base, ensure_ascii=False))
        func(card)
        return card

    def mutate_items(func):
        """带练习题的副本：base 的 practice_items 是空的，出题门要另起一张。"""
        card = json.loads(json.dumps(good, ensure_ascii=False))
        func(card)
        return card

    def _dup_pattern(card):
        card["error_patterns"][1]["pattern"] = card["error_patterns"][0]["pattern"]

    def _all_same_cause(card):
        for item in card["error_patterns"]:
            item["cause_type"] = "运算错误"

    def _answer_numeric_only(card):
        # 前 3/5 题是"光秃秃的数值答案、步骤里也没有算式" → 过半 → W_ANSWER_NUMERIC_ONLY
        for item, answer in zip(card["practice_items"][:3], ("2", "2", "2")):
            item["answer"] = answer
            item["solution_steps"] = "略。"

    def _uniform_cases(source):
        """把三条同伴结论的类型统一成同一种：用来触发 W_ALL_SAME_CAUSE。

        真实案例里三种类型各不相同（那是好事），所以这个告警只能靠合成输入演示。
        """
        copied = json.loads(json.dumps(source, ensure_ascii=False))
        for case in copied:
            case["cause"]["type"] = "运算错误"
        return copied

    def _geometry_cases(source):
        """补一道"中文纯几何题"的合成案例，用来触发 E_EVIDENCE_UNSUPPORTED。

        为什么必须用它：代数题的题面里总有 x、y 这类 ASCII 标识符，而证据里
        也总会提到变量，于是"关键词全找不到"这个条件几乎不可能成立
        （这本身就是该判据的诚实边界：它只对不含 ASCII 符号的题面敏感）。
        """
        copied = json.loads(json.dumps(source, ensure_ascii=False))
        copied.append({
            "id": "T7", "grade_level": "初中",
            "problem": "已知两直线平行，求证同位角相等。",
            "student_solution": "直接当作已成立的结论使用，没有给出理由。",
            "cause": {"type": "论证缺口", "summary": "结论尚未由已有步骤支持，缺少理由。",
                      "method": "assistant_review", "scope": "整段论证",
                      "unresolved_items": []},
        })
        return copied

    def _unsupported_evidence(card):
        """让证据指向 T7，并塞入一个在中文题面里绝不可能出现的标识符。"""
        card["error_patterns"][1]["evidence"] = (
            "[T7#000000000000] 同伴诊断为论证缺口；另外 abc12345 也明显不对。")

    collect("validate", mutate(lambda c: c.pop("strength_kept")))                 # E_FIELDS
    collect("validate", mutate(lambda c: c["error_patterns"].pop()))              # E_COUNT
    collect("validate", mutate(lambda c: c["error_patterns"][0].pop("evidence")))  # E_ITEM_FIELDS
    collect("validate", mutate(lambda c: c["error_patterns"][0].update(pattern="审题不清")))  # 归一化，不该报
    collect("validate", mutate(lambda c: c["error_patterns"][0].update(pattern="莫名其妙")))  # E_PATTERN_UNKNOWN
    collect("validate", mutate(lambda c: c["error_patterns"][0].update(cause_type="心情不好")))  # E_CAUSE_TYPE_UNKNOWN
    collect("validate", mutate(lambda c: c["error_patterns"][0].update(capability_hypothesis="天赋")))  # E_GAP_UNKNOWN
    collect("validate", mutate(lambda c: c["error_patterns"][0].update(
        capability_hypothesis="逻辑完备性")))                                   # W_GAP_MISMATCH
    collect("validate", mutate(_dup_pattern))                                    # E_PATTERN_DUP
    collect("validate", mutate(lambda c: c["error_patterns"][0].update(evidence="没有方括号")))  # E_EVIDENCE_FORM
    collect("validate", mutate(lambda c: c.update(cross_case_commonality="都一样")))  # E_COMMONALITY_NO_IDS
    collect("validate", mutate(lambda c: c.update(capability_profile="暂时没有结论")))  # E_PROFILE_UNKNOWN
    collect("validate", mutate(lambda c: c.update(
        capability_profile="逻辑完备性与步骤留痕与记录都偏弱，待验证")))          # E_PROFILE_MULTI
    collect("validate", mutate(lambda c: c.update(
        capability_profile="步骤留痕与记录偏弱。")))                             # W_TENTATIVE
    collect("validate", mutate(lambda c: c.update(next_training_target="多练练")))  # E_TARGET_UNKNOWN
    collect("validate", mutate(lambda c: c.update(
        next_training_target="过程规范松动与分支穷尽不足")))                     # W_TARGET_MULTI
    collect("validate", mutate(lambda c: c["error_patterns"][0].update(countermeasure="注意一下")))  # W_SHORT + W_TEMPLATE

    def thin_all(card):
        for item in card["error_patterns"]:
            item["case_count"] = 1
    collect("validate", mutate(thin_all))                                        # E_CASE_COUNT_THIN x3
    collect("validate", mutate(lambda c: c["error_patterns"][0].update(case_count=1)))  # E_PATTERN_EVIDENCE_THIN

    collect("audit", base, cases[:1])                                            # E_TOO_FEW_CASES
    collect("audit", mutate(lambda c: c["error_patterns"][2].update(
        evidence="[T3#000000000000] 指纹过期")), cases)                          # E_EVIDENCE_STALE
    collect("audit", mutate(lambda c: [i.update(cause_type="运算错误")
                                       for i in c["error_patterns"]]), _uniform_cases(cases))  # W_ALL_SAME_CAUSE
    collect("audit", mutate(lambda c: c["error_patterns"][0].update(
        countermeasure="你这一步就错了，需要重来。")), cases)                     # A_SINGLE_CASE_CAUSE
    collect("audit", mutate(lambda c: c["error_patterns"][0].update(
        countermeasure="解：先移项再合并，答案是 x=2。")), cases)                 # A_SOLVE
    collect("audit", mutate(lambda c: c["error_patterns"][0].update(
        countermeasure="再讲讲为什么这一步要变号。")), cases)                     # A_PROBE

    dead_cases = [dict(c) for c in cases]
    del dead_cases[0]["cause"]                                                   # E_CAUSE_MISSING
    collect("audit", base, dead_cases)
    unresolved_cases = json.loads(json.dumps(cases, ensure_ascii=False))
    unresolved_cases[0]["cause"]["unresolved_items"] = ["还没确认移项规则"]        # E_CAUSE_UNRESOLVED
    collect("audit", base, unresolved_cases)

    collect("practice", mutate_items(lambda c: c.update(
        practice_authorized=False)))                                             # E_PRACTICE_UNAUTHORIZED
    collect("practice", mutate_items(lambda c: c.update(practice_authorized=True)))  # E_PRACTICE_MISSING（已授权但题目被清空）
    collect("practice", mutate(lambda c: c.update(
        practice_authorized=True, practice_items=[], generation_basis="随便出几道")))  # W_NO_GENERATION_BASIS
    collect("practice", mutate_items(lambda c: c.update(
        practice_items=c["practice_items"][:3])))                                # E_PRACTICE_COUNT
    collect("practice", mutate_items(lambda c: c["practice_items"].append({"id": "P6"})))  # E_PRACTICE_ITEM_FIELDS
    collect("practice", mutate_items(lambda c: [i.update(pattern_ref=9)
                                                for i in c["practice_items"]]), None)  # E_PATTERN_REF_RANGE
    # 下面这几条只在"合成的畸形输入"下才可能触发，真实示例卡不含它们。
    # 注意：这些 collect 调用要放在最后，且其后**不要再打印 hits**（踩过这个坑）。
    collect("audit", mutate(_unsupported_evidence), _geometry_cases(cases))        # E_EVIDENCE_UNSUPPORTED
    collect("audit", mutate(lambda c: c.update(
        cross_case_commonality="第 T1、T3 题都不太顺。")), cases)                 # W_COMMONALITY_WEAK
    collect("practice", mutate_items(lambda c: c["practice_items"][0].update(
        student_prompt="已知二次函数 f(x)=x^2-4x+3，求它与 x 轴交点个数。",
        answer="y=5")), verify_answers=True)                                     # E_ANSWER_UNRELATED
    collect("practice", mutate_items(_answer_numeric_only), verify_answers=True)  # W_ANSWER_NUMERIC_ONLY
    collect("audit", mutate(lambda c: c["error_patterns"][2].update(
        cause_type="条件失效")), cases)                                           # E_CAUSE_TYPE_MISMATCH
    collect("audit", mutate(lambda c: c["error_patterns"][0].update(
        cause_type="逻辑错误")), cases)                                           # E_CAUSE_TYPE_MISMATCH（卡片自称与同伴结论不符）
    collect("practice", mutate_items(lambda c: [
        i.update(student_prompt="解方程 2x+3=7。") for i in c["practice_items"]]))  # E_PRACTICE_DUP
    collect("practice", mutate_items(lambda c: c["practice_items"][0].update(
        answer="", solution_steps="")), verify_answers=True)                     # E_ANSWER_MISSING
    collect("practice", mutate_items(lambda c: c["practice_items"][0].update(
        answer="2x+3=7")), verify_answers=True)                                  # E_ANSWER_IN_PROMPT
    collect("practice", mutate_items(lambda c: c["practice_items"][0].update(
        answer="x=987654")), verify_answers=True)                                # E_ANSWER_UNRELATED
    collect("practice", mutate_items(lambda c: c["practice_items"][0].update(
        student_prompt="若 x>0 且 2x+3=7，求 x 的值。", answer="x=-2")),
        verify_answers=True)                                                     # E_ANSWER_DOMAIN_VIOLATION
    collect("practice", mutate_items(lambda c: c["practice_items"][0].update(
        source_pattern="乱写的模式")))                                            # E_SOURCE_MISMATCH
    collect("practice", mutate_items(lambda c: [i.update(case_count=1)
                                                for i in c["error_patterns"]
                                                if i["pattern"] == "分支穷尽不足"]))  # E_PATTERN_REF_THIN
    collect("practice", mutate(_answer_numeric_only), verify_answers=True)        # W_ANSWER_NUMERIC_ONLY

    expected = {"validate": VALIDATE_CODES, "audit": AUDIT_CODES, "practice": PRACTICE_CODES}
    problems = []
    for action, codes in expected.items():
        missing = [c for c in codes if c not in hits[action]]
        extra = sorted(hits[action] - set(codes))
        print("== %s ==" % action)
        print("   命中 %d/%d 个码" % (len(codes) - len(missing), len(codes)))
        print("   未命中：%s" % (missing or "（无）"))
        if extra:
            print("   清单外的码：%s" % extra)
        problems += missing
    for tmp in ("_tmp_card.json", "_tmp_cases.json"):
        path = BASE / tmp
        if path.exists():
            path.unlink()
    print("\n结论：%s" % ("全部判据都有真实触发" if not problems
                          else "仍有未触发的码：%s" % problems))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
