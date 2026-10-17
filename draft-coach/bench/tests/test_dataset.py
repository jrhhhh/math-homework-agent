# -*- coding: utf-8 -*-
"""数据集完整性与 schema_check 的回归测试。"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

BENCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCH))

from engine import rules_bridge as rb  # noqa: E402
from engine.data import ACTIONS, load_cases, load_config  # noqa: E402


class DatasetTests(unittest.TestCase):
    def test_schema_check_passes(self):
        proc = subprocess.run([sys.executable, str(BENCH / "schema_check.py")],
                              capture_output=True, encoding="utf-8",
                              errors="replace", cwd=str(BENCH))
        payload = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertTrue(payload["passed"])
        self.assertEqual(payload["cases"], 24)
        self.assertEqual(payload["errors"], [])

    def test_case_ids_and_branches_align(self):
        cases = load_cases(BENCH)
        self.assertEqual(len(cases), 24)
        ids = [case["case_id"] for case in cases]
        self.assertEqual(len(ids), len(set(ids)))
        for case in cases:
            branches = case["ground_truth"]["branches"]
            self.assertEqual(sorted(branches), sorted(case["expected_actions"]))
            self.assertTrue(set(case["expected_actions"]) <= set(ACTIONS))

    def test_every_analyze_branch_has_six_dimensions(self):
        for case in load_cases(BENCH):
            for name, gold in case["ground_truth"]["branches"].items():
                if name != "analyze":
                    continue
                self.assertEqual(set(gold["dimensions"]), set(rb.DIM_KEYS),
                                 case["case_id"])
                for key, dim in gold["dimensions"].items():
                    self.assertTrue(dim["acceptable_scores"], (case["case_id"], key))
                    self.assertTrue(dim["evidence_groups"], (case["case_id"], key))

    def test_partition_branches_have_oracle(self):
        partition_cases = [case for case in load_cases(BENCH)
                           if "partition" in case["expected_actions"]]
        self.assertEqual(len(partition_cases), 5)
        for case in partition_cases:
            oracle = case["ground_truth"]["branches"]["partition"]["oracle"]
            self.assertIn("blocks", oracle)
            self.assertIn("confidences", oracle)
            self.assertEqual(len(oracle["confidences"]), oracle["blocks"])

    def test_no_gold_leak_in_cases_file(self):
        raw = (BENCH / "cases.jsonl").read_text(encoding="utf-8").splitlines()
        forbidden = ("acceptable_scores", "evidence_groups", "positive_groups",
                     "branches", "\"gold\"")
        for line in raw:
            for term in forbidden:
                self.assertNotIn(term, line)

    def test_weights_sum_to_100(self):
        config = load_config(BENCH)
        self.assertEqual(sum(config["subset_weights"].values()), 100)
        self.assertTrue(set(config["subset_weights"]) == {
            "layout_core", "evidence_discipline", "partition", "input_modes"})

    def test_splits_cover_all_values(self):
        cases = load_cases(BENCH)
        self.assertEqual({case["split"] for case in cases},
                         {"development", "validation", "test"})


if __name__ == "__main__":
    unittest.main()
