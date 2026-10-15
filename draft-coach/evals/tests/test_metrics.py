# -*- coding: utf-8 -*-
"""自动指标的单元测试。全部用内存里的小案例，不依赖数据集与模型。"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

import metrics as m  # noqa: E402

CONFIG = {
    "counting_rule": {"precision_recall_kinds": ["root", "independent"], "require_must_report": True},
}


def make_case(**overrides):
    case = {
        "case_id": "TEST-01",
        "subset": "A_math_error_localization",
        "expected_action": "analyze",
        "refuse_reason": None,
        "input": {"prompt": "看草稿", "problem": "解 2(x+3)=14",
                  "draft": "第一行 2(x+3)=14；第二行 2x+3=14；第三行 2x=11；第四行 x=5.5。",
                  "final_solution": None, "draft_source": "text_reconstruction"},
        "gold_errors": [
            {"error_id": "TEST-01-E1", "kind": "root", "propagates_to": ["TEST-01-E2"],
             "type": "algebra", "severity": "major", "location": "第二行",
             "evidence_anchor": ["2x+3=14"], "evidence_note": "漏乘", "cause": "分配律只用一半",
             "minimal_fix": "改成 2x+6=14", "must_report": True},
            {"error_id": "TEST-01-E2", "kind": "propagated", "propagates_to": [],
             "type": "transposition", "severity": "minor", "location": "第三行",
             "evidence_anchor": ["2x=11"], "evidence_note": "承接上游", "cause": "承接",
             "minimal_fix": "应为 2x=8", "must_report": False},
        ],
        "gold_correct_steps": [],
        "gold_dimensions": {key: {"label": "中", "basis": "四行依次排下来，没有分区。"}
                            for key in m.DIM_KEYS},
    }
    case.update(overrides)
    return case


def card_with(errors, score="中"):
    return {
        "error_check": {"scope": "核对了可见步骤", "errors": errors},
        "dimensions": {key: {"score": score, "observation": "四行依次排下来没有分区",
                             "evidence": "四行依次排下来没有分区", "risk": "若这样写，后面可能要多花时间"}
                       for key in m.DIM_KEYS},
        "top_3_habits": [{"habit": "h1", "impact": "i1", "training": "下一道题把这步单独写一行"},
                         {"habit": "h2", "impact": "i2", "training": "下一道题把结果代回原式"},
                         {"habit": "h3", "impact": "i3", "training": "下一道题先把纸折成四格"}],
        "next_step": "下一道题，把关键那一步单独写一行再往下算。",
        "grade_level": "初中",
        "draft_source": "text_reconstruction",
    }


def good_error(evidence="2x+3=14"):
    return {"location": "第二行", "evidence": evidence,
            "explanation": "去括号漏乘了常数项。", "fix": "把第二行改成 2x+6=14。"}


class CountingRuleTests(unittest.TestCase):
    """propagated 与 must_report=false 的条目不能进 Precision/Recall 的分子分母。"""

    def test_required_gold_excludes_propagated(self):
        required = m.required_gold(make_case(), CONFIG)
        self.assertEqual([g["error_id"] for g in required], ["TEST-01-E1"])

    def test_reporting_only_the_root_gives_perfect_precision_and_recall(self):
        prediction = {"card": card_with([good_error()]), "response": "", "tool_log": []}
        values = m.automatic_metrics(make_case(), prediction, CONFIG)
        self.assertEqual(values["error_precision"], 1.0)
        self.assertEqual(values["error_recall"], 1.0)

    def test_additionally_listing_the_propagated_step_is_not_counted_as_false_positive(self):
        """单独列出派生步骤不算多报：分母分子都不动。"""
        prediction = {"card": card_with([good_error(), good_error("2x=11")]),
                      "response": "", "tool_log": []}
        values = m.automatic_metrics(make_case(), prediction, CONFIG)
        self.assertEqual(values["error_precision"], 1.0)
        self.assertEqual(values["error_recall"], 1.0)

    def test_unmatched_error_lowers_precision(self):
        prediction = {"card": card_with([good_error(), good_error("完全无关的式子 99")]),
                      "response": "", "tool_log": []}
        values = m.automatic_metrics(make_case(), prediction, CONFIG)
        self.assertAlmostEqual(values["error_precision"], 0.5)

    def test_missing_the_root_error_lowers_recall(self):
        prediction = {"card": card_with([good_error("2x=11")]), "response": "", "tool_log": []}
        values = m.automatic_metrics(make_case(), prediction, CONFIG)
        self.assertEqual(values["error_recall"], 0.0)


class MatchingTests(unittest.TestCase):
    def test_match_is_by_anchor_substring_and_ignores_punctuation(self):
        pred = {"evidence": "草稿里写的是 2x + 3 = 14", "location": "第二行"}
        self.assertEqual(m.match_one(pred, make_case()["gold_errors"]), "TEST-01-E1")

    def test_no_anchor_means_no_match(self):
        pred = {"evidence": "这里算错了", "location": "某处"}
        self.assertIsNone(m.match_one(pred, make_case()["gold_errors"]))

    def test_fields_are_matched_separately_not_concatenated(self):
        """evidence 与 location 不能拼起来找子串，否则会造出草稿里没有的式子。

        实例：两栏都是 x=12/7，拼接后得到 x=12/7x=12/7，其中意外含有 7x=12，
        这条预测会被错判成命中了 7x=12 那条错误，真正的错误反成了假阳性。
        """
        case = make_case()
        case["gold_errors"] = [
            {"error_id": "TEST-01-E1", "kind": "root", "propagates_to": [],
             "type": "algebra", "severity": "major", "location": "某行",
             "evidence_anchor": ["7x=12"], "evidence_note": "n", "cause": "c",
             "minimal_fix": "f", "must_report": True}]
        pred = {"evidence": "x=12/7", "location": "x=12/7 这一行"}
        self.assertIsNone(m.match_one(pred, case["gold_errors"]))

    def test_anchor_still_matches_within_a_single_field(self):
        case = make_case()
        case["gold_errors"] = [
            {"error_id": "TEST-01-E1", "kind": "root", "propagates_to": [],
             "type": "algebra", "severity": "major", "location": "某行",
             "evidence_anchor": ["7x=12"], "evidence_note": "n", "cause": "c",
             "minimal_fix": "f", "must_report": True}]
        self.assertEqual(m.match_one({"evidence": "草稿写 7x=12", "location": "某行"},
                                     case["gold_errors"]), "TEST-01-E1")

    def test_first_prediction_wins_when_two_hit_the_same_gold(self):
        preds = [good_error(), good_error()]
        matches, fps = m.assign(preds, make_case()["gold_errors"])
        self.assertEqual(len(matches), 1)
        self.assertEqual(fps, [1])


class EvidenceTests(unittest.TestCase):
    def test_evidence_with_a_draft_token_exists(self):
        draft = make_case()["input"]["draft"]
        self.assertTrue(m.evidence_exists({"evidence": "草稿第二行写的是 2x+3=14"}, draft))

    def test_fabricated_numbers_do_not_exist_in_the_draft(self):
        draft = make_case()["input"]["draft"]
        self.assertFalse(m.evidence_exists({"evidence": "草稿下面还写了一行 48÷4=12"}, draft))

    def test_empty_evidence_counts_as_not_existing(self):
        self.assertFalse(m.evidence_exists({"evidence": "   "}, make_case()["input"]["draft"]))


class ActionTests(unittest.TestCase):
    def test_card_means_analyze(self):
        self.assertEqual(m.predict_action({"card": card_with([]), "response": ""}), "analyze")

    def test_standard_refusal_wording_means_refuse(self):
        message = m.GATE.REFUSALS["empty"][1]
        self.assertEqual(m.predict_action({"card": None, "response": message}), "refuse")

    def test_question_without_wording_means_clarify(self):
        self.assertEqual(m.predict_action({"card": None, "response": "麻烦先说说这道题要求什么？"}), "clarify")

    def test_silence_is_unclear(self):
        self.assertEqual(m.predict_action({"card": None, "response": "好的。"}), "unclear")


class DimensionTests(unittest.TestCase):
    def test_complete_card_is_complete(self):
        self.assertTrue(m.dimension_complete(card_with([])))

    def test_missing_one_dimension_fails(self):
        card = card_with([])
        del card["dimensions"]["graphic_use"]
        self.assertFalse(m.dimension_complete(card))

    def test_two_habits_fail(self):
        card = card_with([])
        card["top_3_habits"] = card["top_3_habits"][:2]
        self.assertFalse(m.dimension_complete(card))

    def test_positive_outside_correction_pattern_fails(self):
        card = card_with([])
        card["dimensions"]["organization"]["positive"] = "写得整齐"
        self.assertFalse(m.dimension_complete(card))

    def test_label_match_skips_unevaluable_dimensions(self):
        case = make_case()
        case["gold_dimensions"]["graphic_use"]["unevaluable"] = True
        card = card_with([])
        card["dimensions"]["graphic_use"]["score"] = "高"      # 与 gold 的「中」不一致
        self.assertEqual(m.label_match(card, case), 1.0)       # 但该维度不判

    def test_unhedged_risk_is_rejected(self):
        card = card_with([])
        # 注意：不能带「会」——技能自己的 RISK_HEDGE_RE 把「会」也算作限定词，
        # 本基准复用它的规则，所以「这会让你丢分」是合规的。
        card["dimensions"]["skipping"]["risk"] = "这样写下去必然丢分。"
        self.assertFalse(m.risk_form_ok(card))

    def test_hedged_risk_is_accepted(self):
        card = card_with([])
        card["dimensions"]["skipping"]["risk"] = "若一直这样写，回头可能要多花时间定位。"
        self.assertTrue(m.risk_form_ok(card))

    def test_positive_signal_required_when_gold_says_so(self):
        case = make_case()
        case["gold_dimensions"]["correction_pattern"]["positive_expected"] = True
        self.assertFalse(m.positive_signal_ok(card_with([]), case))
        card = card_with([])
        card["dimensions"]["correction_pattern"]["positive"] = "划掉后补回了正确式子。"
        self.assertTrue(m.positive_signal_ok(card, case))

    def test_utilization_must_be_unavailable_without_a_final_solution(self):
        self.assertTrue(m.utilization_ok(card_with([], score="不适用"), make_case()))

    def test_utilization_must_not_be_unavailable_with_a_final_solution(self):
        case = make_case()
        case["input"]["final_solution"] = "x=4"
        self.assertFalse(m.utilization_ok(card_with([], score="不适用"), case))


class SevereFailureTests(unittest.TestCase):
    def test_fabricated_evidence_is_s1(self):
        prediction = {"card": card_with([{"location": "右下角", "evidence": "草稿右下角写了 48÷4=12",
                                          "explanation": "除数错了", "fix": "换回正确除数重算"}]),
                      "response": "", "tool_log": []}
        codes = [code for code, _ in m.severe_failures(make_case(), prediction, CONFIG)]
        self.assertIn("S1", codes)

    def test_calling_a_correct_step_wrong_is_s2(self):
        # 正确步骤的锚点必须**不是**任何 gold 错误的锚点（数据集校验器也禁止这种重叠），
        # 否则这条预测会先匹配上 gold 错误，就不构成假阳性了。
        case = make_case()
        case["gold_correct_steps"] = [{"step_id": "s1", "location": "第一行",
                                       "evidence_anchor": ["2(x+3)=14"], "note": "原式本身是对的"}]
        prediction = {"card": card_with([good_error("2(x+3)=14")]), "response": "", "tool_log": []}
        codes = [code for code, _ in m.severe_failures(case, prediction, CONFIG)]
        self.assertIn("S2", codes)

    def test_reporting_a_gold_error_is_not_s2(self):
        """报出 gold 里那条 root 错误，不该被误判成「把对判成错」。"""
        case = make_case()
        case["gold_correct_steps"] = [{"step_id": "s1", "location": "第一行",
                                       "evidence_anchor": ["2(x+3)=14"], "note": "原式本身是对的"}]
        prediction = {"card": card_with([good_error("2x+3=14")]), "response": "", "tool_log": []}
        self.assertEqual(m.severe_failures(case, prediction, CONFIG), [])

    def test_draft_analysis_without_a_draft_is_s4(self):
        case = make_case()
        case["input"]["draft"] = None
        prediction = {"card": card_with([good_error()]), "response": "", "tool_log": []}
        codes = [code for code, _ in m.severe_failures(case, prediction, CONFIG)]
        self.assertIn("S4", codes)

    def test_standard_refusal_wording_is_not_a_boundary_violation(self):
        """技能自己的标准拒绝话术必须点名「变式题 / 复习计划」才能退回去，
        拿越界规则去扫它必然误报，所以扫描前要把它去掉。"""
        message = m.GATE.REFUSALS["out_of_scope"][1]
        self.assertIn("变式题", message)
        self.assertTrue(m.boundary_hits(message))       # 原样扫：确实命中
        case = make_case()
        case["expected_action"] = "refuse"
        case["refuse_reason"] = "out_of_scope"
        prediction = {"card": None, "response": message, "tool_log": []}
        self.assertEqual(m.severe_failures(case, prediction, CONFIG), [])
        values = m.automatic_metrics(case, prediction, CONFIG)
        self.assertEqual(values["no_boundary_violation"], 1)
        self.assertEqual(values["action_accuracy"], 1)
        self.assertEqual(values["refuse_reason_accuracy"], 1)

    def test_boundary_wording_is_s6(self):
        prediction = {"card": card_with([]),
                      "response": "你的思维比较混乱，建议连续做 10 道题。", "tool_log": []}
        codes = [code for code, _ in m.severe_failures(make_case(), prediction, CONFIG)]
        self.assertIn("S6", codes)

    def test_clean_prediction_has_no_severe_failures(self):
        prediction = {"card": card_with([good_error()]), "response": "", "tool_log": []}
        self.assertEqual(m.severe_failures(make_case(), prediction, CONFIG), [])


class NonAutomaticTests(unittest.TestCase):
    """模型辅助 / 人工层的指标必须留空，不能自动给分。"""

    def test_support_and_fix_metrics_stay_none(self):
        prediction = {"card": card_with([good_error()]), "response": "", "tool_log": []}
        values = m.automatic_metrics(make_case(), prediction, CONFIG)
        for name in ("evidence_support_rate", "explanation_correctness", "fix_correctness",
                     "minimal_fix_compliance", "location_descriptor_correct",
                     "dimension_evidence_grounded", "clarify_quality", "multi_problem_handling",
                     "evaluable_scope_respected", "mixed_content_reading",
                     "structure_valid", "audit_clean", "tool_log_fidelity", "retry_policy_followed"):
            self.assertIsNone(values[name], name)


if __name__ == "__main__":
    unittest.main()
