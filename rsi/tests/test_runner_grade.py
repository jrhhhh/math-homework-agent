# -*- coding: utf-8 -*-
"""rsi.runner 与 rsi.grade 的回归测试。

跑法（仓库根目录）：
    python -m unittest discover -s rsi/tests -p 'test_*.py'
"""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "math-solver" / "bench"))

from engine.data import load_jsonl  # noqa: E402
from make_fixture_predictions import build_bad, build_oracle  # noqa: E402
from rsi import grade, runner  # noqa: E402

CASES = {case["case_id"]: case
         for case in load_jsonl(REPO / "math-solver" / "bench" / "cases.jsonl")}


def write_predictions(predictions, path):
    payload = {
        "arm": "skill_gates",
        "model": "test-fixture",
        "run_id": "test-run",
        "predictions": predictions,
    }
    Path(path).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class GradeTests(unittest.TestCase):
    def test_oracle_grades_one(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "oracle.json"
            write_predictions(build_oracle(), path)
            result = grade.grade_paths([path])
        self.assertAlmostEqual(result["g"], 1.0, places=4)
        self.assertEqual(result["severe_count_max"], 0)
        self.assertEqual(result["case_count"], 51)

    def test_bad_fixture_reproduces_benchmark(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            write_predictions(build_bad(build_oracle()), path)
            result = grade.grade_paths([path])
        self.assertAlmostEqual(result["g"], 0.7611, places=4)
        self.assertEqual(result["severe_count_max"], 12)
        self.assertEqual(result["case_count"], 51)

    def test_multiple_seeds_take_mean(self):
        oracle = build_oracle()
        bad = build_bad(build_oracle())
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "oracle.json"
            second = Path(directory) / "bad.json"
            write_predictions(oracle, first)
            write_predictions(bad, second)
            result = grade.grade_paths([first, second])
        self.assertAlmostEqual(result["g"], (1.0 + 0.7611) / 2, places=3)
        self.assertEqual(result["severe_count_max"], 12)
        self.assertEqual(result["run_count"], 2)


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.skill = runner.SkillBundle(REPO / "math-solver")
        self.budget = runner.Budget()
        self.oracle = {item["case_id"]: item for item in build_oracle()}

    def test_replays_structure_gate_and_overwrites_claimed_exit_code(self):
        prediction = copy.deepcopy(self.oracle["MATH-01"])
        prediction["tool_log"] = [{
            "command": "python3 scripts/validate_output.py validate --card x.json --strict",
            "exit_code": 1,
        }]
        adapter = runner.FixtureAdapter([prediction])
        record = runner.Runner(self.skill, adapter, self.budget).run_case(
            CASES["MATH-01"])
        self.assertEqual(record["action"], "solve")
        self.assertEqual(record["tool_log"][0]["exit_code"], 0)

    def test_drops_output_for_route_action(self):
        prediction = copy.deepcopy(self.oracle["MATH-29"])
        prediction["output"] = {"status": "solved"}
        adapter = runner.FixtureAdapter([prediction])
        record = runner.Runner(self.skill, adapter, self.budget).run_case(
            CASES["MATH-29"])
        self.assertEqual(record["action"], "route")
        self.assertEqual(record["route_to"], "math-error-diagnosis")
        self.assertNotIn("output", record)
        self.assertIn("runner_notes", record)

    def test_marks_over_budget_usage(self):
        def fake(_request):
            return {
                "action": "clarify",
                "reply": "请把题面打成文字。",
                "usage": {"total_tokens": self.budget.max_tokens + 1},
            }

        adapter = runner.CallableAdapter(fake)
        record = runner.Runner(self.skill, adapter, self.budget).run_case(
            CASES["MATH-32"])
        self.assertTrue(record["over_budget"])

    def test_missing_prediction_is_omitted(self):
        adapter = runner.FixtureAdapter([])
        record = runner.Runner(self.skill, adapter, self.budget).run_case(
            CASES["MATH-01"])
        self.assertIsNone(record)

    def test_skill_fingerprint_tracks_editable_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "skill"
            (root / "references").mkdir(parents=True)
            (root / "SKILL.md").write_text("version one", encoding="utf-8")
            first = runner.SkillBundle(root).fingerprint()
            (root / "SKILL.md").write_text("version two", encoding="utf-8")
            second = runner.SkillBundle(root).fingerprint()
        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
