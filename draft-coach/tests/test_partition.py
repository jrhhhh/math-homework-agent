"""题目分区（partition）出口的版面分块门测试。"""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "draft-coach/scripts/partition_check.py"
EXAMPLE = ROOT / "draft-coach/example/partition_sheet.json"


def run_validate(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, encoding="utf-8", errors="replace")


def example():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def codes(payload):
    return [item["code"] for item in payload.get("errors", [])]


def warning_codes(payload):
    return [item["code"] for item in payload.get("warnings", [])]


def validate(payload, strict=False):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "partition.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        args = ["validate", "--payload", str(path)]
        if strict:
            args.append("--strict")
        result = run_validate(*args)
    return result.returncode, json.loads(result.stdout)


class PartitionGateTests(unittest.TestCase):
    def test_example_passes(self):
        code, payload = validate(example(), strict=True)
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["errors"], [])
        self.assertEqual(payload["warnings"], [])

    def test_missing_field_is_rejected(self):
        data = example()
        data.pop("uncertainty")
        code, payload = validate(data)
        self.assertEqual(code, 1)
        self.assertIn("E_MISSING_FIELD", codes(payload))

    def test_card_fields_are_not_allowed(self):
        data = example()
        data["dimensions"] = {}
        data["error_check"] = {"scope": "x", "errors": []}
        code, payload = validate(data)
        self.assertEqual(code, 1)
        self.assertEqual(codes(payload).count("E_EXTRA_FIELD"), 2)

    def test_bad_action_and_source(self):
        data = example()
        data["action"] = "triage"
        data["block_source"] = "ocr_candidate"
        code, payload = validate(data)
        self.assertEqual(code, 1)
        self.assertIn("E_BAD_ACTION", codes(payload))
        self.assertIn("E_BAD_SOURCE", codes(payload))

    def test_block_count_bounds(self):
        data = example()
        data["blocks"] = []
        code, payload = validate(data)
        self.assertEqual(code, 1)
        self.assertIn("E_BLOCK_COUNT", codes(payload))

        data = example()
        data["blocks"] = [copy.deepcopy(data["blocks"][0]) for _ in range(13)]
        code, payload = validate(data)
        self.assertEqual(code, 1)
        self.assertIn("E_BLOCK_COUNT", codes(payload))

    def test_duplicate_block_id(self):
        data = example()
        data["blocks"][1]["block_id"] = data["blocks"][0]["block_id"]
        code, payload = validate(data)
        self.assertEqual(code, 1)
        self.assertIn("E_DUPLICATE_BLOCK_ID", codes(payload))

    def test_bad_confidence(self):
        data = example()
        data["blocks"][0]["confidence"] = "很高"
        code, payload = validate(data)
        self.assertEqual(code, 1)
        self.assertIn("E_BAD_CONFIDENCE", codes(payload))

    def test_estimate_must_be_within_block_count(self):
        data = example()
        data["estimated_problem_count"] = 4
        code, payload = validate(data)
        self.assertEqual(code, 1)
        self.assertIn("E_BAD_ESTIMATE", codes(payload))

    def test_range_must_contain_estimate(self):
        data = example()
        data["count_range"] = [3, 3]
        code, payload = validate(data)
        self.assertEqual(code, 1)
        self.assertIn("E_RANGE_MISMATCH", codes(payload))

    def test_confirmation_question_is_required(self):
        data = example()
        data["confirmation_question"] = "看完了。"
        code, payload = validate(data)
        self.assertEqual(code, 1)
        self.assertIn("E_NO_CONFIRMATION", codes(payload))

    def test_vague_limitations_are_rejected(self):
        data = example()
        data["limitations"] = ["仅供参考"]
        code, payload = validate(data)
        self.assertEqual(code, 1)
        self.assertIn("E_LIMITATION_VAGUE", codes(payload))

    def test_assertive_partition_wording_is_rejected(self):
        data = example()
        data["confirmation_question"] = "这就是 3 道题，已经分好了。"
        code, payload = validate(data)
        self.assertEqual(code, 1)
        self.assertIn("E_ASSERTIVE_PARTITION", codes(payload))

    def test_error_claim_is_rejected(self):
        data = example()
        data["blocks"][0]["note"] = "这一行算错了。"
        code, payload = validate(data)
        self.assertEqual(code, 1)
        self.assertIn("E_ERROR_CLAIM_IN_PARTITION", codes(payload))

    def test_ocr_claim_is_rejected(self):
        data = example()
        data["blocks"][0]["note"] = "我看出来这行写的是 x=2。"
        code, payload = validate(data)
        self.assertEqual(code, 1)
        self.assertIn("E_OCR_CLAIM_IN_PARTITION", codes(payload))

    def test_overconfidence_warns_only_under_strict(self):
        data = example()
        for block in data["blocks"]:
            block["confidence"] = "高"
        data["count_range"] = [3, 3]
        data["estimated_problem_count"] = 3
        code, payload = validate(data)
        self.assertEqual(code, 0, payload)
        self.assertIn("W_OVERCONFIDENT_PARTITION", warning_codes(payload))

        code, _ = validate(data, strict=True)
        self.assertEqual(code, 1)

    def test_invalid_json_uses_exit_code_two(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text("not JSON", encoding="utf-8")
            result = run_validate("validate", "--payload", str(path))
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
