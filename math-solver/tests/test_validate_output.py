"""math-solver 结构门（validate）的回归测试。

与 draft-coach/tests 一样，用 sys.executable 起子进程，避开本机 PATH 上
python3 可能是应用商店占位程序的问题。
"""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
VALIDATE = ROOT / "math-solver/scripts/validate_output.py"
EXAMPLES = ROOT / "math-solver/example"

SOLVED = "sqrt_equation_solved.json"
AMBIGUOUS = "ambiguous_needs_clarification.json"


def run_validate(*args):
    # 门脚本把 stdout 重配成 UTF-8，而 Windows 默认 locale 是 GBK；
    # 读取端必须显式指定 encoding，否则会拿 GBK 解 UTF-8 而炸掉。
    return subprocess.run([sys.executable, str(VALIDATE), *args],
                          capture_output=True, encoding="utf-8", errors="replace")


def example(name):
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def validate(mutate=None, strict=False, name=SOLVED):
    data = example(name)
    if mutate:
        mutate(data)
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "output.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        args = ["validate", "--card", str(path)]
        if strict:
            args.append("--strict")
        result = run_validate(*args)
        payload = json.loads(result.stdout) if result.stdout else {}
        return result.returncode, payload


def codes(payload):
    return [item["code"] for item in payload.get("errors", [])]


def warning_codes(payload):
    return [item["code"] for item in payload.get("warnings", [])]


class MathSolverValidateTests(unittest.TestCase):
    def test_real_examples_pass_clean(self):
        for name in (SOLVED, AMBIGUOUS):
            with self.subTest(example=name):
                result = run_validate("validate", "--card", str(EXAMPLES / name), "--strict")
                payload = json.loads(result.stdout)
                self.assertEqual(result.returncode, 0, result.stdout)
                self.assertEqual(payload["errors"], [])
                self.assertEqual(payload["warnings"], [])
                self.assertTrue(payload["passed"])

    def test_missing_top_level_field(self):
        code, payload = validate(lambda d: d.pop("teaching_notes"))
        self.assertEqual(code, 1)
        self.assertIn("E_MISSING_FIELD", codes(payload))

    def test_extra_top_level_field_is_rejected(self):
        code, payload = validate(lambda d: d.update(confidence=0.99))
        self.assertEqual(code, 1)
        self.assertIn("E_EXTRA_FIELD", codes(payload))
        self.assertIn("E_CONFIDENCE_FIELD", codes(payload))

    def test_confidence_field_nested(self):
        code, payload = validate(lambda d: d["teaching_notes"].update(probability=0.99))
        self.assertEqual(code, 1)
        self.assertIn("E_CONFIDENCE_FIELD", codes(payload))

    def test_bad_top_level_status(self):
        code, payload = validate(lambda d: d.update(status="correct"))
        self.assertEqual(code, 1)
        self.assertIn("E_BAD_STATUS", codes(payload))

    def test_solved_requires_passed_verification(self):
        code, payload = validate(lambda d: d["verification"].update(status="needs_review"))
        self.assertEqual(code, 1)
        self.assertIn("E_STATUS_VERIFY_CONFLICT", codes(payload))

    def test_passed_with_failed_check(self):
        code, payload = validate(lambda d: d["verification"]["checks"][0].update(status="failed"))
        self.assertEqual(code, 1)
        self.assertIn("E_PASSED_WITH_FAILED_CHECK", codes(payload))

    def test_passed_with_incomplete_check(self):
        code, payload = validate(lambda d: d["verification"]["checks"][0].update(status="not_completed"))
        self.assertEqual(code, 1)
        self.assertIn("E_PASSED_WITH_INCOMPLETE_CHECK", codes(payload))

    def test_passed_with_issues(self):
        code, payload = validate(lambda d: d["verification"].update(issues=["仍有问题"]))
        self.assertEqual(code, 1)
        self.assertIn("E_PASSED_WITH_ISSUES", codes(payload))

    def test_passed_without_checks(self):
        code, payload = validate(lambda d: d["verification"].update(checks=[]))
        self.assertEqual(code, 1)
        self.assertIn("E_PASSED_WITHOUT_CHECKS", codes(payload))

    def test_bad_check_status(self):
        code, payload = validate(lambda d: d["verification"]["checks"][0].update(status="ok"))
        self.assertEqual(code, 1)
        self.assertIn("E_BAD_CHECK_STATUS", codes(payload))

    def test_bad_step_number(self):
        code, payload = validate(lambda d: d["solution"]["derivation"][0].update(step=0))
        self.assertEqual(code, 1)
        self.assertIn("E_BAD_STEP", codes(payload))

    def test_derivation_must_be_a_list(self):
        code, payload = validate(lambda d: d["solution"].update(derivation={}))
        self.assertEqual(code, 1)
        self.assertIn("E_TYPE", codes(payload))

    def test_empty_answer_for_solved(self):
        code, payload = validate(lambda d: d["solution"].update(answer=""))
        self.assertEqual(code, 1)
        self.assertIn("E_EMPTY", codes(payload))
        self.assertIn("E_SOLVED_WITHOUT_ANSWER", codes(payload))

    def test_step_sequence_warning_and_strict(self):
        mutate = lambda d: d["solution"]["derivation"][1].update(step=5)
        code, payload = validate(mutate)
        self.assertEqual(code, 0, payload)
        self.assertIn("W_STEP_SEQUENCE", warning_codes(payload))
        strict_code, strict_payload = validate(mutate, strict=True)
        self.assertEqual(strict_code, 1)
        self.assertIn("W_STEP_SEQUENCE", warning_codes(strict_payload))

    def test_partial_solved_with_passed_is_warning(self):
        mutate = lambda d: d.update(status="partially_solved")
        code, payload = validate(mutate)
        self.assertEqual(code, 0, payload)
        self.assertIn("W_PARTIAL_PASSED", warning_codes(payload))
        strict_code, strict_payload = validate(mutate, strict=True)
        self.assertEqual(strict_code, 1)
        self.assertIn("W_PARTIAL_PASSED", warning_codes(strict_payload))

    def test_needs_clarification_requires_reason(self):
        def mutate(d):
            d["problem"]["ambiguities"] = []
            d["verification"]["issues"] = []
        code, payload = validate(mutate, name=AMBIGUOUS)
        self.assertEqual(code, 1)
        self.assertIn("E_CLARIFY_WITHOUT_REASON", codes(payload))

    def test_bad_json_is_input_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text("{not json", encoding="utf-8")
            result = run_validate("validate", "--card", str(path))
            self.assertEqual(result.returncode, 2)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["errors"][0]["code"], "E_INPUT")

    def test_non_object_root_is_input_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "array.json"
            path.write_text("[]", encoding="utf-8")
            result = run_validate("validate", "--card", str(path))
            self.assertEqual(result.returncode, 2)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["errors"][0]["code"], "E_INPUT")

    def test_missing_file_is_input_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "does-not-exist.json"
            result = run_validate("validate", "--card", str(path))
            self.assertEqual(result.returncode, 2)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["errors"][0]["code"], "E_INPUT")


if __name__ == "__main__":
    unittest.main()
