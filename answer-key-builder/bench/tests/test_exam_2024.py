# -*- coding: utf-8 -*-
"""2024 新高考Ⅰ卷 19 条案例与 solution 夹具的回归测试。"""

import subprocess
import sys
import unittest
from pathlib import Path

BENCH = Path(__file__).resolve().parents[1]
SKILL = BENCH.parent
sys.path.insert(0, str(BENCH))

from engine.data import index_by_id, load_jsonl  # noqa: E402
from tools.exam_2024 import EXAM_CASES  # noqa: E402

EXPECTED_IDS = [f"MATH-{number:02d}" for number in range(33, 52)]


class Exam2024Tests(unittest.TestCase):
    def test_19_exam_cases_present(self):
        cases = index_by_id(load_jsonl(BENCH / "cases.jsonl"))
        for case_id in EXPECTED_IDS:
            self.assertIn(case_id, cases, case_id)
            case = cases[case_id]
            self.assertEqual(case["expected_action"], "solve", case_id)
            self.assertEqual(case["expected_status"], "solved", case_id)
            self.assertIn("2024_xgk1", case["tags"], case_id)
        self.assertEqual(len(EXPECTED_IDS), 19)

    def test_exam_solution_files_pass_validate(self):
        for case in EXAM_CASES:
            with self.subTest(case_id=case["case_id"]):
                card = BENCH / case["_source_file"]
                self.assertTrue(card.exists(), card)
                result = subprocess.run(
                    [sys.executable, str(SKILL / "scripts" / "validate_output.py"),
                     "validate", "--card", str(card), "--strict"],
                    capture_output=True, encoding="utf-8", errors="replace",
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
