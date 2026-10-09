import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("handoff_check", ROOT / "scripts/handoff_check.py")
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)
PROBLEM = "求 x²-5x+6=0 的根。"
SOLUTION = "用求根公式：x=(5±√1)/2，所以 x1=3，x2=2。"


def packet():
    return dict(protocol_version=1, problem_id="quadratic-1", grade_level="高中",
                problem=PROBLEM, student_solution=SOLUTION,
                solution_version=GATE.version(PROBLEM, SOLUTION), solution_source="student",
                result_status="correct", process_status="valid", review_complete=True,
                verification=dict(method="assistant_review", scope="完整题目与全部步骤", unresolved_items=[]),
                requested_action="refine", feedback_mode="process_check")


class HandoffTests(unittest.TestCase):
    def test_valid_current_student_solution(self):
        result = GATE.route(packet(), PROBLEM, SOLUTION)
        self.assertTrue(result["eligible"])
        self.assertEqual(result["next_skill"], "solution-refiner")

    def test_rejects_insufficient_states(self):
        cases = [("result_status", "incorrect"), ("result_status", "unknown"),
                 ("process_status", "invalid"), ("process_status", "gap"),
                 ("process_status", "not_provided"), ("process_status", "unknown"),
                 ("solution_source", "assistant_repair"), ("review_complete", False),
                 ("requested_action", "check"), ("feedback_mode", "hint")]
        for key, value in cases:
            with self.subTest(key=key, value=value):
                data = packet()
                data[key] = value
                result = GATE.route(data, PROBLEM, SOLUTION)
                self.assertFalse(result["eligible"])
                self.assertIsNone(result["next_skill"])
        for updates in [dict(method="numeric_only"), dict(method="none"), dict(scope=""),
                        dict(unresolved_items=["竖直直线尚未检查"])]:
            with self.subTest(verification=updates):
                data = packet()
                data["verification"].update(updates)
                self.assertFalse(GATE.route(data, PROBLEM, SOLUTION)["eligible"])

    def test_version_and_current_text_cannot_be_reused(self):
        for p, s, grade in [(PROBLEM+"限定x>0", SOLUTION, "高中"),
                            (PROBLEM, SOLUTION+"改用因式分解", "高中"),
                            (PROBLEM, SOLUTION, "初中"), (PROBLEM, "", "高中")]:
            with self.subTest(problem=p, solution=s, grade=grade):
                self.assertFalse(GATE.route(packet(), p, s, grade)["eligible"])
        data = packet()
        data["solution_version"] = "0"*64
        self.assertFalse(GATE.route(data, PROBLEM, SOLUTION)["eligible"])

    def test_missing_fields_and_boolean_strings_rejected(self):
        data = packet()
        del data["verification"]
        with self.assertRaises(ValueError):
            GATE.route(data, PROBLEM, SOLUTION)
        data = packet()
        data["review_complete"] = "true"
        with self.assertRaises(ValueError):
            GATE.route(data, PROBLEM, SOLUTION)

    def test_cli_real_exit_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            p, s, h = directory/"problem.txt", directory/"solution.txt", directory/"handoff.json"
            p.write_text(PROBLEM)
            s.write_text(SOLUTION)
            args = ["python3", str(ROOT/"scripts/handoff_check.py"), "route",
                    "--handoff", str(h), "--problem-file", str(p), "--solution-file", str(s)]
            for value, expected in [(packet(), 0), ({**packet(), "process_status": "gap"}, 1), ({}, 2)]:
                h.write_text(json.dumps(value, ensure_ascii=False))
                result = subprocess.run(args, text=True, capture_output=True)
                self.assertEqual(result.returncode, expected, result.stdout)
                json.loads(result.stdout)
            h.write_text("not JSON")
            self.assertEqual(subprocess.run(args, capture_output=True).returncode, 2)
            p.unlink()
            self.assertEqual(subprocess.run(args, capture_output=True).returncode, 2)

    def test_card_schema_and_audit_preserved(self):
        checker = ROOT/"solution-refiner/solution_card_check.py"
        for filename, expected in [("correct_card.json", (0, 0)),
                                   ("mixed_diagnosis_card.json", (0, 1)),
                                   ("mathematically_wrong_card.json", (0, 0))]:
            card = ROOT/"solution-refiner/example"/filename
            results = [subprocess.run(["python3", str(checker), "validate", "--card", str(card)],
                                      text=True, capture_output=True),
                       subprocess.run(["python3", str(checker), "audit", "--card", str(card),
                                       "--problem", PROBLEM, "--solution", SOLUTION, "--strict"],
                                      text=True, capture_output=True)]
            with self.subTest(card=filename):
                self.assertEqual(tuple(r.returncode for r in results), expected)
                for r in results:
                    json.loads(r.stdout)
        # 错误数学卡能过两门是诚实边界，不应包装成数学核验成功。
        self.assertNotEqual(-1-6, -5)

    def test_handoff_metadata_not_allowed_in_card(self):
        card = json.loads((ROOT/"solution-refiner/example/correct_card.json").read_text())
        card["process_status"] = "valid"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"card.json"
            path.write_text(json.dumps(card, ensure_ascii=False))
            r = subprocess.run(["python3", str(ROOT/"solution-refiner/solution_card_check.py"),
                                "validate", "--card", str(path)], text=True, capture_output=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("E_EXTRA_FIELD", [e["code"] for e in json.loads(r.stdout)["errors"]])


if __name__ == "__main__":
    unittest.main()
