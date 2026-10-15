# -*- coding: utf-8 -*-
"""人工 / 模型辅助评审接口的测试。"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

import human_review  # noqa: E402

CONFIG = {
    "subset_metrics": {"C_dimension_analysis": ["dimension_label_match",
                                                "dimension_evidence_grounded"]},
    "metric_layers": {"dimension_label_match": "automatic",
                      "dimension_evidence_grounded": "model_assisted",
                      "retry_policy_followed": "human"},
}

CASE = {
    "case_id": "DIM-99", "subset": "C_dimension_analysis",
    "input": {"draft": "草稿内容", "prompt": "看看草稿"},
}


class ExportTests(unittest.TestCase):
    def test_export_skips_cases_with_no_metrics_for_that_layer(self):
        """human 层在本配置里只有 retry_policy_followed，它不属于 C 子集，
        所以这个案例没有任何该层该管的指标 → 整条不列，而不是列一堆空指标。"""
        payload = human_review.export_template(CONFIG, [CASE], "human", "skill_gates")
        self.assertEqual(payload["layer"], "human")
        self.assertEqual(payload["ratings"], [])
        self.assertEqual(payload["instructions"][0][:12], "只填 true / fa")

    def test_export_lists_model_assisted_metrics_for_the_right_subset(self):
        payload = human_review.export_template(CONFIG, [CASE], "model_assisted", "skill_gates")
        self.assertEqual(len(payload["ratings"]), 1)
        self.assertEqual(sorted(payload["ratings"][0]["metrics"]), ["dimension_evidence_grounded"])
        self.assertIsNone(payload["ratings"][0]["metrics"]["dimension_evidence_grounded"])
        self.assertIn("草稿内容", payload["ratings"][0]["draft"])
        self.assertTrue(payload["instructions"])

    def test_blank_is_not_the_same_as_false(self):
        payload = human_review.export_template(CONFIG, [CASE], "model_assisted", "skill_gates")
        result = human_review.check_review(payload, CONFIG)
        self.assertTrue(result["passed"])
        self.assertEqual(result["ratings_blank"], 1)
        self.assertEqual(result["ratings_filled"], 0)


class CheckTests(unittest.TestCase):
    def _payload(self, value):
        return {"layer": "model_assisted", "reviewer": "r",
                "ratings": [{"case_id": "DIM-99",
                             "metrics": {"dimension_evidence_grounded": value}}]}

    def test_true_and_false_are_accepted(self):
        for value in (True, False):
            result = human_review.check_review(self._payload(value), CONFIG)
            self.assertTrue(result["passed"], value)
            self.assertEqual(result["ratings_filled"], 1)

    def test_non_boolean_is_rejected(self):
        for bad in (1, 0, "true", "是"):
            result = human_review.check_review(self._payload(bad), CONFIG)
            self.assertFalse(result["passed"])
            self.assertTrue(result["problems"])

    def test_unknown_metric_is_rejected(self):
        payload = {"layer": "human", "ratings": [{"case_id": "DIM-99",
                                                 "metrics": {"没有这个指标": True}}]}
        self.assertFalse(human_review.check_review(payload, CONFIG)["passed"])

    def test_bad_layer_is_rejected(self):
        payload = {"layer": "automatic", "ratings": []}
        self.assertFalse(human_review.check_review(payload, CONFIG)["passed"])

    def test_duplicate_case_is_rejected(self):
        payload = {"layer": "human",
                   "ratings": [{"case_id": "DIM-99", "metrics": {}},
                               {"case_id": "DIM-99", "metrics": {}}]}
        self.assertFalse(human_review.check_review(payload, CONFIG)["passed"])


class LayerCoverageTests(unittest.TestCase):
    def test_metrics_for_layer_is_exhaustive_and_disjoint(self):
        known = set(CONFIG["metric_layers"])
        union = set()
        for layer in human_review.LAYERS:
            names = set(human_review.metrics_for_layer(CONFIG, layer))
            self.assertFalse(union & names, "两层里有重复指标：%s" % (union & names))
            union |= names
        self.assertTrue(union <= known)


if __name__ == "__main__":
    unittest.main()
