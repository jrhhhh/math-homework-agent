# -*- coding: utf-8 -*-
"""数据集完整性测试：跑真实数据集，结构、锚点自洽、防泄漏、指标名都必须成立。

这些断言**不判数学**。数学正确性只能人工或模型辅助复核，见 docs/DESIGN.md。
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

from cases import SUBSETS, load_cases  # noqa: E402
import schema_check  # noqa: E402

EVALS = ROOT          # evals/ 里放着 cases.jsonl 与 ground_truth.jsonl


class DatasetIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = load_cases(EVALS)
        cls.ids, cls.issues = schema_check.check_dataset(EVALS)

    def test_dataset_is_not_empty(self):
        self.assertGreaterEqual(len(self.cases), 30,
                                "第一阶段要求至少 30 个可实际使用的案例")

    def test_no_structural_errors(self):
        messages = ["%s: %s %s" % (e["case_id"], e["code"], e["message"])
                    for e in self.issues.errors]
        self.assertEqual(messages, [], "\n".join(messages))

    def test_no_warnings_either(self):
        """警告也要清掉：它们往往意味着标注口径开始漂。"""
        messages = ["%s: %s %s" % (w["case_id"], w["code"], w["message"])
                    for w in self.issues.warnings]
        self.assertEqual(messages, [], "\n".join(messages))

    def test_all_six_subsets_are_populated(self):
        present = {case["subset"] for case in self.cases}
        self.assertEqual(present, set(SUBSETS))

    def test_both_splits_are_populated(self):
        splits = {case["split"] for case in self.cases}
        self.assertEqual(splits, {"development", "validation"})

    def test_case_ids_are_unique(self):
        ids = [case["case_id"] for case in self.cases]
        self.assertEqual(len(ids), len(set(ids)))

    def test_templates_do_not_span_splits(self):
        """同一模板（含只换数字的近重复）必须整体落在同一 split。"""
        buckets = {}
        for case in self.cases:
            buckets.setdefault(case["template_id"], set()).add(case["split"])
        leaks = {t: s for t, s in buckets.items() if len(s) > 1}
        self.assertEqual(leaks, {})

    def test_every_anchor_is_literal_in_its_draft(self):
        """这是数据自身的「证据必须有草稿依据」，校验器已经强查，这里再钉一遍。"""
        import cases as ds
        for case in self.cases:
            draft = ds.normalise_strict(case["input"].get("draft") or "")
            anchors = [a for err in case["gold_errors"] for a in err["evidence_anchor"]]
            anchors += [a for step in case["gold_correct_steps"] for a in step["evidence_anchor"]]
            for anchor in anchors:
                self.assertIn(ds.normalise_strict(anchor), draft,
                              "%s 的锚点 %r 不在草稿里" % (case["case_id"], anchor))

    def test_every_case_declares_a_known_metric(self):
        known = set(__import__("json").loads(
            (ROOT / "config.json").read_text(encoding="utf-8"))["metric_layers"])
        for case in self.cases:
            for name in case.get("metrics") or []:
                self.assertIn(name, known, "%s 用了未知指标 %s" % (case["case_id"], name))

    def test_analyze_cases_carry_full_ground_truth(self):
        for case in self.cases:
            if case["expected_action"] != "analyze":
                continue
            self.assertIn("gold_dimensions", case, case["case_id"])
            self.assertEqual(len(case["gold_dimensions"]), 6, case["case_id"])
            self.assertTrue(case["forbidden_behaviors"], case["case_id"])

    def test_non_analyze_cases_do_not_carry_dimensions(self):
        for case in self.cases:
            if case["expected_action"] == "analyze":
                continue
            self.assertNotIn("gold_dimensions", case,
                             "%s 不产出卡片，不该有六维标准答案" % case["case_id"])

    def test_cases_without_a_draft_have_no_gold_errors(self):
        for case in self.cases:
            if (case["input"].get("draft") or "").strip():
                continue
            self.assertEqual(case["gold_errors"], [],
                             "%s 没有草稿却标了错误" % case["case_id"])

    def test_progressed_errors_point_at_existing_propagated_entries(self):
        for case in self.cases:
            by_id = {e["error_id"]: e for e in case["gold_errors"]}
            for error in case["gold_errors"]:
                for target in error["propagates_to"]:
                    self.assertIn(target, by_id, case["case_id"])
                    self.assertEqual(by_id[target]["kind"], "propagated", case["case_id"])


class ValidatorSelfTest(unittest.TestCase):
    """校验器必须真的会拒收坏案例——否则它只是一份摆设。"""

    def test_validator_flags_missing_field_and_bad_enum(self):
        case = {
            "case_id": "MATH-99", "template_id": "tpl-x", "subset": "A_math_error_localization",
            "split": "development", "category": "c", "difficulty": "impossible",
            "grade_level": "初中",
            "input": {"prompt": "p", "problem": None, "draft": None, "final_solution": None,
                      "draft_source": "text_reconstruction"},
            "expected_action": "analyze", "refuse_reason": None, "gold_errors": [],
            "gold_correct_steps": [], "expected_behaviors": ["x"], "forbidden_behaviors": ["y"],
            "severity": "low", "provenance": "synthetic", "notes": "n",
        }
        issues = schema_check.Issues()
        schema_check.check_case(case, issues)
        codes = {e["code"] for e in issues.errors}
        self.assertIn("E_ENUM", codes)                       # difficulty 非法
        self.assertIn("E_DRAFT_SOURCE_CONFLICT", codes)      # 没有草稿却说不是 absent
        self.assertIn("E_REQUIRED", codes)                   # analyze 缺 gold_dimensions


if __name__ == "__main__":
    unittest.main()
