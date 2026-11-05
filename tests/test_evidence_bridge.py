"""learning-evidence-bridge 聚合脚本的回归测试。"""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "learning-evidence-bridge/scripts/evidence.py"


def payload(grade_level, item_grade=None):
    item = {
        "id": "I1",
        "problem": "解 x+1=2",
        "objective": "解一元一次方程",
        "submission": {
            "id": "S1",
            "revision": 1,
            "version": "v1",
            "state": "ready",
            "data": {
                "problem": "解 x+1=2",
                "source": "student",
                "grade_level": grade_level,
                "mode": "check",
            },
            "result": {
                "status": "ready",
                "output": {"result": {"judgment": "correct", "first_error": None}},
            },
        },
    }
    if item_grade is not None:
        item["grade_level"] = item_grade
    return {"items": [item]}


def run(data):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "input.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return subprocess.run([sys.executable, str(SCRIPT), str(path)],
                              capture_output=True)


class EvidenceBridgeTests(unittest.TestCase):
    def test_cli_emits_utf8_even_with_non_ascii_payload(self):
        result = run(payload("高中"))
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        text = result.stdout.decode("utf-8")
        self.assertIn("解一元一次方程", text)
        self.assertIn("仅本机任务当前提交", text)

    def test_item_grade_is_compared_instead_of_hardcoding_high_school(self):
        result = run(payload("初中", item_grade="初中"))
        data = json.loads(result.stdout.decode("utf-8"))
        self.assertEqual(data["items"][0]["state"], "correct")

    def test_grade_mismatch_still_marks_binding_changed(self):
        result = run(payload("初中", item_grade="高中"))
        data = json.loads(result.stdout.decode("utf-8"))
        self.assertEqual(data["items"][0]["state"], "binding_changed")


if __name__ == "__main__":
    unittest.main()
