# -*- coding: utf-8 -*-
"""rsi.validate_diff 的回归测试。"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from rsi import validate_diff  # noqa: E402


def make_skill(root: Path) -> None:
    (root / "references").mkdir(parents=True)
    (root / "bench").mkdir()
    (root / "scripts").mkdir()
    (root / "SKILL.md").write_text("line one\nline two\n", encoding="utf-8")
    (root / "references" / "a.md").write_text("reference\n", encoding="utf-8")
    (root / "bench" / "cases.jsonl").write_text("{}\n", encoding="utf-8")
    (root / "scripts" / "gate.py").write_text("print('gate')\n", encoding="utf-8")


class ValidateDiffTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.base = self.root / "base"
        self.candidate = self.root / "candidate"
        make_skill(self.base)
        shutil.copytree(self.base, self.candidate)

    def tearDown(self):
        self._tmp.cleanup()

    def test_small_skill_edit_is_valid(self):
        (self.candidate / "SKILL.md").write_text(
            "line one\nline two changed\n", encoding="utf-8")
        result = validate_diff.validate_candidate(self.base, self.candidate)
        self.assertTrue(result["ok"], result["violations"])
        self.assertEqual(result["changed_lines"], 2)

    def test_frozen_path_is_rejected(self):
        (self.candidate / "bench" / "cases.jsonl").write_text(
            '{"changed": true}\n', encoding="utf-8")
        result = validate_diff.validate_candidate(self.base, self.candidate)
        self.assertFalse(result["ok"])
        self.assertTrue(any("冻结路径" in item for item in result["violations"]))

    def test_non_editable_path_is_rejected(self):
        (self.candidate / "README.md").write_text("notes\n", encoding="utf-8")
        result = validate_diff.validate_candidate(self.base, self.candidate)
        self.assertFalse(result["ok"])
        self.assertTrue(any("不在可编辑面" in item for item in result["violations"]))

    def test_added_reference_is_valid(self):
        (self.candidate / "references" / "b.md").write_text(
            "new reference\n", encoding="utf-8")
        result = validate_diff.validate_candidate(self.base, self.candidate)
        self.assertTrue(result["ok"], result["violations"])
        self.assertEqual(result["changed_lines"], 1)

    def test_deleted_reference_is_rejected(self):
        (self.candidate / "references" / "a.md").unlink()
        result = validate_diff.validate_candidate(self.base, self.candidate)
        self.assertFalse(result["ok"])
        self.assertTrue(any("不允许删除" in item for item in result["violations"]))

    def test_nested_reference_path_is_not_editable(self):
        nested = self.candidate / "references" / "sub"
        nested.mkdir()
        (nested / "x.md").write_text("nested\n", encoding="utf-8")
        result = validate_diff.validate_candidate(self.base, self.candidate)
        self.assertFalse(result["ok"])
        self.assertTrue(any("不在可编辑面" in item for item in result["violations"]))

    def test_line_limit_is_enforced(self):
        (self.candidate / "SKILL.md").write_text(
            "\n".join(f"line {index}" for index in range(50)) + "\n",
            encoding="utf-8")
        result = validate_diff.validate_candidate(
            self.base, self.candidate, max_changed_lines=10)
        self.assertFalse(result["ok"])
        self.assertTrue(any("超过上限" in item for item in result["violations"]))

    def test_missing_candidate_skill_md_is_input_error(self):
        (self.candidate / "SKILL.md").unlink()
        with self.assertRaises(validate_diff.DiffError):
            validate_diff.validate_candidate(self.base, self.candidate)


if __name__ == "__main__":
    unittest.main()
