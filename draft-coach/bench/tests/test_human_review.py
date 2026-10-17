# -*- coding: utf-8 -*-
"""人工评审层的导出与回读测试。"""

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


class HumanReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.tmp.name)
        cls.predictions = cls.dir / "oracle.json"
        proc = run("make_fixture_predictions.py", "--mode", "oracle",
                   "--out", str(cls.predictions))
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_export_has_all_cases_and_null_reviews(self):
        out = self.dir / "template.json"
        proc = run("engine/human_review.py", "export",
                   "--predictions", str(self.predictions), "--out", str(out))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(len(payload["items"]), 24)
        for item in payload["items"]:
            for question in ("observation_faithful", "habit_appropriate",
                             "next_step_usable"):
                self.assertIsNone(item["review"][question])

    def test_merge_computes_rates_and_ignores_null(self):
        template = self.dir / "template2.json"
        run("engine/human_review.py", "export",
            "--predictions", str(self.predictions), "--out", str(template))
        payload = json.loads(template.read_text(encoding="utf-8"))
        payload["items"][0]["review"].update(
            observation_faithful=True, habit_appropriate=True, next_step_usable=True)
        payload["items"][1]["review"].update(
            observation_faithful=True, habit_appropriate=False, next_step_usable=None)
        payload["items"][2]["review"].update(
            observation_faithful=False, habit_appropriate=None, next_step_usable=True)
        filled = self.dir / "filled.json"
        filled.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        out = self.dir / "summary.json"
        proc = run("engine/human_review.py", "merge", "--reviews", str(filled),
                   "--out", str(out))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        summary = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(summary["items"], 24)
        self.assertAlmostEqual(summary["overall"]["observation_faithful"]["rate"], 2 / 3)
        self.assertAlmostEqual(summary["overall"]["habit_appropriate"]["rate"], 0.5)
        self.assertAlmostEqual(summary["overall"]["next_step_usable"]["rate"], 1.0)
        for question in ("observation_faithful", "habit_appropriate",
                         "next_step_usable"):
            self.assertNotIn("rate_human", summary["overall"][question])

    def test_merge_rejects_non_boolean(self):
        template = self.dir / "template3.json"
        run("engine/human_review.py", "export",
            "--predictions", str(self.predictions), "--out", str(template))
        payload = json.loads(template.read_text(encoding="utf-8"))
        payload["items"][0]["review"]["observation_faithful"] = "true"
        bad = self.dir / "bad.json"
        bad.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        proc = run("engine/human_review.py", "merge", "--reviews", str(bad),
                   "--out", str(self.dir / "ignored.json"))
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
