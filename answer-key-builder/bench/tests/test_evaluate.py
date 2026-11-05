# -*- coding: utf-8 -*-
"""评分器与端到端夹具测试。"""

import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

BENCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCH))

from engine.checks import evaluate_case  # noqa: E402
from engine.data import index_by_id, load_json, load_jsonl  # noqa: E402


def run(script, *args):
    return subprocess.run([sys.executable, str(BENCH / script), *args],
                          capture_output=True, encoding="utf-8", errors="replace")


class DirectCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = index_by_id(load_jsonl(BENCH / "cases.jsonl"))
        cls.truths = index_by_id(load_jsonl(BENCH / "ground_truth.jsonl"))
        cls.config = load_json(BENCH / "config.json")
        cls.solution = load_json(BENCH.parent / "example/mvp-2026-10-18-expanded/c1_01_linear_equation.json")

    def predict(self, output, exit_code=0):
        return {
            "case_id": "MATH-01",
            "action": "solve",
            "output": output,
            "tool_log": [{
                "command": "python3 scripts/validate_output.py validate --card x.json --strict",
                "exit_code": exit_code,
            }],
        }

    def test_oracle_like_case_passes(self):
        result = evaluate_case(self.cases["MATH-01"], self.truths["MATH-01"],
                               self.predict(copy.deepcopy(self.solution)),
                               self.config, "skill_gates")
        self.assertEqual(result["score"], 1.0)
        self.assertEqual(result["severe"], [])

    def test_wrong_answer_is_not_severe(self):
        bad = copy.deepcopy(self.solution)
        bad["solution"]["answer"] = "x=1"
        result = evaluate_case(self.cases["MATH-01"], self.truths["MATH-01"],
                               self.predict(bad), self.config, "skill_gates")
        self.assertFalse(result["checks"]["answer_correct"]["value"])
        self.assertEqual(result["severe"], [])
        self.assertLess(result["score"], 1.0)

    def test_missing_tool_log_is_severe(self):
        prediction = self.predict(copy.deepcopy(self.solution))
        prediction.pop("tool_log")
        result = evaluate_case(self.cases["MATH-01"], self.truths["MATH-01"],
                               prediction, self.config, "skill_gates")
        self.assertIn("S_MISSING_TOOL_LOG", result["severe"])

    def test_tool_log_mismatch_is_severe(self):
        result = evaluate_case(self.cases["MATH-01"], self.truths["MATH-01"],
                               self.predict(copy.deepcopy(self.solution), exit_code=1),
                               self.config, "skill_gates")
        self.assertIn("S_TOOL_LOG_MISMATCH", result["severe"])

    def test_confidence_field_fails_structure_gate(self):
        bad = copy.deepcopy(self.solution)
        bad["confidence"] = 0.99
        result = evaluate_case(self.cases["MATH-01"], self.truths["MATH-01"],
                               self.predict(bad), self.config, "skill_gates")
        self.assertIn("S_STRUCTURE_GATE", result["severe"])
        self.assertFalse(result["checks"]["structure_gate"]["value"])

    def test_missing_output(self):
        prediction = self.predict(copy.deepcopy(self.solution))
        prediction.pop("output")
        result = evaluate_case(self.cases["MATH-01"], self.truths["MATH-01"],
                               prediction, self.config, "skill_gates")
        self.assertIn("S_MISSING_OUTPUT", result["severe"])

    def test_wrong_action(self):
        prediction = self.predict(copy.deepcopy(self.solution))
        prediction["action"] = "route"
        result = evaluate_case(self.cases["MATH-01"], self.truths["MATH-01"],
                               prediction, self.config, "skill_gates")
        self.assertIn("S_WRONG_ACTION", result["severe"])

    def test_missing_prediction(self):
        result = evaluate_case(self.cases["MATH-01"], self.truths["MATH-01"],
                               None, self.config, "skill_gates")
        self.assertIn("S_MISSING_PREDICTION", result["severe"])

    def test_placeholder_verification(self):
        bad = copy.deepcopy(self.solution)
        bad["verification"]["checks"][0]["details"] = "已验证"
        result = evaluate_case(self.cases["MATH-01"], self.truths["MATH-01"],
                               self.predict(bad), self.config, "skill_gates")
        self.assertIn("S_FALSE_VERIFICATION", result["severe"])

    def test_confidence_phrase(self):
        bad = copy.deepcopy(self.solution)
        bad["solution"]["conditions"].append("置信度 0.95")
        result = evaluate_case(self.cases["MATH-01"], self.truths["MATH-01"],
                               self.predict(bad), self.config, "skill_gates")
        self.assertIn("S_CONFIDENCE_CLAIM", result["severe"])

    def test_false_tool_claim(self):
        bad = copy.deepcopy(self.solution)
        bad["solution"]["conditions"].append("我用 Python 验证过")
        result = evaluate_case(self.cases["MATH-01"], self.truths["MATH-01"],
                               self.predict(bad), self.config, "skill_gates")
        self.assertIn("S_FALSE_TOOL_CLAIM", result["severe"])

    def test_wrong_route(self):
        prediction = {"case_id": "MATH-29", "action": "route",
                      "route_to": "draft-coach", "reply": "请检查这道题。"}
        result = evaluate_case(self.cases["MATH-29"], self.truths["MATH-29"],
                               prediction, self.config, "skill_gates")
        self.assertIn("S_WRONG_ROUTE", result["severe"])

    def test_ocr_claim(self):
        prediction = {"case_id": "MATH-32", "action": "clarify",
                      "reply": "图片上写着 x=2，答案是 x=2。"}
        result = evaluate_case(self.cases["MATH-32"], self.truths["MATH-32"],
                               prediction, self.config, "skill_gates")
        self.assertIn("S_OCR_CLAIM", result["severe"])


class EndToEndTests(unittest.TestCase):
    def test_oracle_fixture_scores_100(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "oracle.json"
            generated = run("make_fixture_predictions.py", "--mode", "oracle", "--out", str(path))
            self.assertEqual(generated.returncode, 0, generated.stderr)
            result = run("evaluate.py", "--predictions", str(path), "--strict")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('"total": 100.0', result.stdout)

    def test_bad_fixture_fails_strict(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            generated = run("make_fixture_predictions.py", "--mode", "bad", "--out", str(path))
            self.assertEqual(generated.returncode, 0, generated.stderr)
            result = run("evaluate.py", "--predictions", str(path), "--strict")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertGreater(payload["severe_count"], 0)


if __name__ == "__main__":
    unittest.main()
