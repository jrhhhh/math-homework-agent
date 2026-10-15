# -*- coding: utf-8 -*-
"""打分与汇总的单元测试：None 不得被当成 0 分或满分，权重必须如实呈现。"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

import scoring  # noqa: E402

CONFIG = {
    "subset_weights": {"A_math_error_localization": 0.5, "B_evidence_fidelity": 0.5},
    "subset_metrics": {"A_math_error_localization": ["error_precision"],
                       "B_evidence_fidelity": ["evidence_existence_rate"]},
    "metric_layers": {"error_precision": "automatic",
                      "evidence_existence_rate": "automatic",
                      "evidence_support_rate": "model_assisted"},
    "counting_rule": {},
    "proportion_ci": {"z": 1.96},
}


class RateTests(unittest.TestCase):
    def test_none_is_not_counted_in_the_denominator(self):
        stats = scoring.rate([1, 0, None, None])
        self.assertEqual(stats["numerator"], 1)
        self.assertEqual(stats["denominator"], 2)
        self.assertEqual(stats["rate"], 0.5)

    def test_all_none_is_reported_as_not_run_not_as_zero(self):
        stats = scoring.rate([None, None])
        self.assertIsNone(stats["rate"])
        self.assertEqual(stats["status"], "未运行或不适用")

    def test_wilson_interval_brackets_the_estimate(self):
        ci = scoring.wilson(3, 10)
        self.assertLess(ci["low"], 0.3)
        self.assertGreater(ci["high"], 0.3)

    def test_fractional_values_are_averaged_not_counted_as_successes(self):
        """案例级结果是分数的指标（如 tool_log_fidelity）不能被抬成满分。"""
        stats = scoring.rate([0.5, 1.0])
        self.assertEqual(stats["numerator"], 1.5)
        self.assertEqual(stats["denominator"], 2)
        self.assertEqual(stats["rate"], 0.75)
        self.assertIsNone(stats["ci"])
        self.assertIn("分数值", stats["ci_note"])

    def test_binary_values_still_get_an_interval(self):
        stats = scoring.rate([1, 0])
        self.assertIsNotNone(stats["ci"])

    def test_small_samples_get_wide_intervals(self):
        narrow = scoring.wilson(50, 100)
        wide = scoring.wilson(1, 2)
        self.assertGreater(wide["high"] - wide["low"], narrow["high"] - narrow["low"])


class MergeTests(unittest.TestCase):
    def test_boolean_values_are_accepted(self):
        table = scoring.merge_external([{"case_id": "X", "metrics": {"evidence_support_rate": True}}],
                                       "model_assisted", {"evidence_support_rate"})
        self.assertEqual(table[("X", "evidence_support_rate")], 1)

    def test_null_is_skipped_not_treated_as_false(self):
        table = scoring.merge_external([{"case_id": "X", "metrics": {"evidence_support_rate": None}}],
                                       "model_assisted", {"evidence_support_rate"})
        self.assertEqual(table, {})

    def test_non_boolean_is_rejected(self):
        for bad in (1, 0, "true", "是"):
            with self.assertRaises(ValueError):
                scoring.merge_external([{"case_id": "X", "metrics": {"evidence_support_rate": bad}}],
                                       "model_assisted", {"evidence_support_rate"})

    def test_unknown_metric_is_rejected(self):
        with self.assertRaises(ValueError):
            scoring.merge_external([{"case_id": "X", "metrics": {"没有这个指标": True}}],
                                   "model_assisted", {"evidence_support_rate"})


def result(subset, precision, existence):
    return {"case": {"case_id": "c", "subset": subset, "difficulty": "easy",
                     "category": "cat", "input": {"draft_source": "text_reconstruction"}},
            "arm": "skill", "metrics": {"error_precision": precision,
                                        "evidence_existence_rate": existence},
            "severe": []}


class AggregateTests(unittest.TestCase):
    def test_subset_scores_use_only_computable_metrics(self):
        report = scoring.aggregate([result("A_math_error_localization", 1, None),
                                    result("A_math_error_localization", 0, None)], CONFIG)
        subset = report["subsets"]["A_math_error_localization"]
        self.assertEqual(subset["score"], 50.0)
        self.assertEqual(subset["metric_detail"]["error_precision"]["denominator"], 2)

    def test_unrun_subsets_are_excluded_and_renormalisation_is_disclosed(self):
        report = scoring.aggregate([result("A_math_error_localization", 1, None)], CONFIG)
        self.assertTrue(report["total"]["renormalised"])
        self.assertIn("B_evidence_fidelity", report["total"]["excluded_subsets"])
        self.assertEqual(report["total"]["score"], 100.0)
        self.assertIn("重新归一化", report["total"]["note"])

    def test_no_renormalisation_when_every_subset_scores(self):
        report = scoring.aggregate([result("A_math_error_localization", 1, None),
                                    result("B_evidence_fidelity", None, 0)], CONFIG)
        self.assertFalse(report["total"]["renormalised"])
        self.assertEqual(report["total"]["score"], 50.0)

    def test_layer_breakdown_keeps_layers_apart(self):
        report = scoring.aggregate([result("A_math_error_localization", 1, None)], CONFIG)
        layers = report["subsets"]["A_math_error_localization"]["by_layer"]
        self.assertEqual(layers["automatic"]["denominator"], 1)
        self.assertEqual(layers["model_assisted"]["status"], "未运行或不适用")
        self.assertEqual(layers["human"]["status"], "未运行或不适用")

    def test_severe_failures_are_listed_and_counted(self):
        item = result("A_math_error_localization", 1, None)
        item["severe"] = [("S1", "编造证据")]
        report = scoring.aggregate([item], CONFIG)
        self.assertEqual(report["severe_failure_count"], 1)
        self.assertEqual(report["severe_failures"][0]["code"], "S1")

    def test_nothing_computable_gives_no_total(self):
        report = scoring.aggregate([result("A_math_error_localization", None, None)], CONFIG)
        self.assertIsNone(report["total"]["score"])

    def test_strata_are_reported_per_difficulty_and_source(self):
        report = scoring.aggregate([result("A_math_error_localization", 1, None)], CONFIG)
        self.assertIn("easy", report["strata"]["difficulty"])
        self.assertIn("text_reconstruction", report["strata"]["draft_source"])
        self.assertEqual(report["strata"]["difficulty"]["easy"]["cases"], 1)


if __name__ == "__main__":
    unittest.main()
