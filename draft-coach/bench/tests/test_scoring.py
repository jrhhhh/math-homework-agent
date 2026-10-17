# -*- coding: utf-8 -*-
"""聚合与权重的单元测试。"""

import sys
import unittest
from pathlib import Path

BENCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCH))

from engine.data import load_config  # noqa: E402
from engine.scoring import aggregate, rate, wilson  # noqa: E402


CONFIG = load_config(BENCH)
SUBSETS = list(CONFIG["subset_weights"])


def result(subset, score, severe=None, checks=None):
    return {
        "case_id": "X-" + subset,
        "subset": subset,
        "split": "development",
        "difficulty": "easy",
        "grade_level": "高中",
        "category": "test",
        "draft_source": "text_reconstruction",
        "action": "analyze",
        "score": score,
        "severe": severe or [],
        "checks": checks or [],
    }


class ScoringTests(unittest.TestCase):
    def test_all_full_scores_total_100(self):
        results = [result(subset, 1.0) for subset in SUBSETS]
        report = aggregate(results, CONFIG)
        self.assertAlmostEqual(report["total"]["score"], 100.0)
        self.assertEqual(report["total"]["excluded_subsets"], [])
        self.assertEqual(report["hard_pass"]["passed"], len(SUBSETS))

    def test_weight_is_applied(self):
        results = [result(subset, 1.0) for subset in SUBSETS]
        results[0] = result(SUBSETS[0], 0.0)
        report = aggregate(results, CONFIG)
        expected = 100.0 - CONFIG["subset_weights"][SUBSETS[0]]
        self.assertAlmostEqual(report["total"]["score"], expected)

    def test_none_subset_is_excluded_and_renormalised(self):
        results = [result(subset, 1.0) for subset in SUBSETS]
        results[0] = result(SUBSETS[0], None)
        report = aggregate(results, CONFIG)
        self.assertAlmostEqual(report["total"]["score"], 100.0)
        self.assertTrue(report["total"]["renormalised"])
        self.assertEqual(report["total"]["excluded_subsets"], [SUBSETS[0]])

    def test_severe_failures_are_reported_separately(self):
        severe = [{"code": "S_ERROR_CLAIM", "message": "boom"}]
        results = [result(subset, 1.0) for subset in SUBSETS]
        results[0] = result(SUBSETS[0], 0.0, severe=severe)
        report = aggregate(results, CONFIG)
        self.assertEqual(report["severe_failure_count"], 1)
        self.assertEqual(report["hard_pass"]["passed"], len(SUBSETS) - 1)
        # 严重失败不因为其他案例满分而消失
        self.assertLess(report["total"]["score"], 100.0)

    def test_check_rate_ignores_none(self):
        checks = [{"name": "action_correct", "value": 1},
                  {"name": "action_correct", "value": None},
                  {"name": "action_correct", "value": 0}]
        report = aggregate([result(SUBSETS[0], 0.5, checks=checks)], CONFIG)
        data = report["check_rates"]["action_correct"]
        self.assertEqual(data["denominator"], 2)
        self.assertAlmostEqual(data["rate"], 0.5)

    def test_wilson_bounds(self):
        interval = wilson(8, 10)
        self.assertLess(interval["low"], 0.8)
        self.assertGreater(interval["high"], 0.8)
        self.assertIsNone(wilson(0, 0))

    def test_rate_with_fractional_values_has_no_ci(self):
        data = rate([0.5, 1.0])
        self.assertIsNone(data["ci"])
        self.assertAlmostEqual(data["rate"], 0.75)

    def test_coverage_includes_grade_level(self):
        report = aggregate([result(SUBSETS[0], 1.0)], CONFIG)
        self.assertEqual(report["coverage"]["by_grade_level"], {"高中": 1})
        self.assertIn("grade_level", report["strata"])


if __name__ == "__main__":
    unittest.main()
