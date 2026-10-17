# -*- coding: utf-8 -*-
"""端到端：夹具生成 → 评测 → 报告 → 退出码。"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BENCH = Path(__file__).resolve().parents[1]


def run(*args):
    return subprocess.run([sys.executable, *args], cwd=str(BENCH),
                          capture_output=True, encoding="utf-8", errors="replace")


class EndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.tmp.name)
        cls.fixtures = {}
        for mode in ("oracle", "bad", "empty"):
            path = cls.dir / ("%s.json" % mode)
            proc = run("make_fixture_predictions.py", "--mode", mode,
                       "--out", str(path))
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr)
            cls.fixtures[mode] = path

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def evaluate(self, mode, *extra):
        out = self.dir / ("%s.report.json" % mode)
        md = self.dir / ("%s.report.md" % mode)
        proc = run("evaluate.py", "--predictions", str(self.fixtures[mode]),
                   "--out", str(out), "--markdown", str(md), *extra)
        payload = json.loads(out.read_text(encoding="utf-8")) if out.is_file() else None
        return proc, payload, out, md

    def test_oracle_full_score(self):
        proc, report, out, md = self.evaluate("oracle")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertAlmostEqual(report["total"]["score"], 100.0, places=6)
        self.assertEqual(report["severe_failure_count"], 0)
        self.assertEqual(report["hard_pass"]["passed"], 24)
        self.assertTrue(out.is_file())
        self.assertTrue(md.is_file())
        self.assertIn("Draft Coach", md.read_text(encoding="utf-8"))

    def test_oracle_strict_exit_zero(self):
        proc, report, _out, _md = self.evaluate("oracle", "--strict")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(report["severe_failure_count"], 0)

    def test_bad_fixture_triggers_expected_severe_codes(self):
        proc, report, _out, _md = self.evaluate("bad")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertGreater(report["severe_failure_count"], 0)
        codes = {item["code"] for item in report["severe_failures"]}
        for expected in ("S_ERROR_CLAIM", "S_PARTITION_ASSERTION",
                         "S_OCR_FABRICATION", "S_BAIT_PRODUCED",
                         "S_TOOL_LOG_MISMATCH"):
            self.assertIn(expected, codes)

    def test_bad_fixture_strict_exits_one(self):
        proc, _report, _out, _md = self.evaluate("bad", "--strict")
        self.assertEqual(proc.returncode, 1, proc.stderr)

    def test_empty_predictions_score_zero(self):
        proc, report, _out, _md = self.evaluate("empty")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(report["total"]["score"], 0.0)
        self.assertEqual(report["hard_pass"]["passed"], 0)
        self.assertEqual(report["severe_failure_count"], 24)

    def test_fail_under_exits_one(self):
        proc, _report, _out, _md = self.evaluate("oracle", "--fail-under", "100.01")
        self.assertEqual(proc.returncode, 1, proc.stderr)

    def test_split_filter(self):
        proc, report, _out, _md = self.evaluate("oracle", "--split", "test")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(report["cases_evaluated"], 3)
        self.assertAlmostEqual(report["total"]["score"], 100.0, places=6)

    def test_subset_filter(self):
        proc, report, _out, _md = self.evaluate("oracle", "--subset", "layout_core")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(report["cases_evaluated"], 10)
        self.assertEqual(report["total"]["excluded_subsets"],
                         sorted({"evidence_discipline", "partition", "input_modes"}))

    def test_unknown_case_id_is_invalid_input(self):
        bad_path = self.dir / "unknown.json"
        bad_path.write_text(json.dumps({
            "predictions": [{"case_id": "NOPE-99", "action": "analyze"}]
        }), encoding="utf-8")
        proc = run("evaluate.py", "--predictions", str(bad_path))
        self.assertEqual(proc.returncode, 2, proc.stderr)


if __name__ == "__main__":
    unittest.main()
