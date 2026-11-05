# -*- coding: utf-8 -*-
"""schema_check.py 的数据自洽测试。"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

BENCH = Path(__file__).resolve().parents[1]


def run(*args):
    return subprocess.run([sys.executable, str(BENCH / "schema_check.py"), *args],
                          capture_output=True, encoding="utf-8", errors="replace")


class SchemaCheckTests(unittest.TestCase):
    def test_real_dataset_passes(self):
        result = run()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn('"ok": true', result.stdout)

    def test_duplicate_case_id_fails(self):
        import json
        cases = [json.loads(line) for line in
                 (BENCH / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        cases.append(dict(cases[0]))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.jsonl"
            path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in cases) + "\n",
                            encoding="utf-8")
            result = run("--cases", str(path))
            self.assertEqual(result.returncode, 1)
            self.assertIn("E_DUP_CASE_ID", result.stdout)

    def test_missing_ground_truth_fails(self):
        import json
        truths = [json.loads(line) for line in
                  (BENCH / "ground_truth.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        truths = truths[:-1]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ground_truth.jsonl"
            path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in truths) + "\n",
                            encoding="utf-8")
            result = run("--ground-truth", str(path))
            self.assertEqual(result.returncode, 1)
            self.assertIn("E_MISSING_TRUTH", result.stdout)


if __name__ == "__main__":
    unittest.main()
