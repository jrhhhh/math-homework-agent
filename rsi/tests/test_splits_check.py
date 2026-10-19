# -*- coding: utf-8 -*-
"""rsi.splits_check 的回归测试。"""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from rsi import splits_check  # noqa: E402

BENCH = REPO / "math-solver" / "bench"


def case(case_id, split, problem, action="solve", status="solved",
         subset="answer_core", tags=None):
    return {
        "case_id": case_id,
        "subset": subset,
        "split": split,
        "grade_level": "高中",
        "input": {
            "problem": problem,
            "student_attempt": None,
            "draft": None,
            "requested_method": None,
        },
        "expected_action": action,
        "expected_status": status,
        "expected_route": None,
        "tags": tags or ["test"],
    }


def truth(case_id, answer_check=None, must_include=None):
    return {
        "case_id": case_id,
        "answer_check": answer_check or {"kind": "value_set", "values": [2]},
        "required_checks": [],
        "required_terms": [],
        "forbidden_terms": [],
        "must_include": must_include or [],
        "rationale": "test fixture",
    }


def write_split(root: Path, name: str, cases, truths, manifest=None):
    path = root / name
    path.mkdir(parents=True, exist_ok=True)
    (path / "cases.jsonl").write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in cases) + "\n",
        encoding="utf-8")
    (path / "ground_truth.jsonl").write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in truths) + "\n",
        encoding="utf-8")
    if manifest is not None:
        (path / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8")


class SplitsCheckTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "splits"
        self.root.mkdir()
        self.data = {
            "selection": (
                [case("SEL-01", "selection", "解方程：2x+1=5。")],
                [truth("SEL-01")],
            ),
            "sealed_id": (
                [case("SEAL-01", "sealed_id", "解方程：3x-4=8。")],
                [truth("SEAL-01", answer_check={"kind": "value_set", "values": [4]})],
            ),
            "ood": (
                [case("OOD-01", "ood",
                      "证明：任意整数 n，n^2+n 为偶数。")],
                [truth("OOD-01",
                       answer_check={"kind": "text_forms",
                                     "groups": [["偶数"]]})],
            ),
            "probes": (
                [case("PROBE-01", "probes",
                      "已知三角形两边为 3 和 4，求第三边。",
                      action="clarify", status=None, subset="boundary_routing",
                      tags=["probe:ambiguous"])],
                [truth("PROBE-01", answer_check={"kind": "clarify"},
                       must_include=[["条件"]])],
            ),
        }
        self.write_all()

    def tearDown(self):
        self._tmp.cleanup()

    def write_all(self):
        for name, (cases, truths) in self.data.items():
            write_split(self.root, name, cases, truths, manifest={
                "name": name,
                "source": "test",
                "created_at": "2026-10-19",
                "contaminated": False,
            })

    def validate(self):
        return splits_check.validate_splits(self.root, BENCH)

    def test_valid_splits_pass(self):
        result = self.validate()
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(result["splits"]["selection"]["case_count"], 1)

    def test_cross_split_case_id_is_rejected(self):
        sealed_case = copy.deepcopy(self.data["sealed_id"][0][0])
        sealed_truth = copy.deepcopy(self.data["sealed_id"][1][0])
        sealed_case["case_id"] = "SEL-01"
        sealed_case["input"]["problem"] = "另一道题：x+1=3。"
        sealed_truth["case_id"] = "SEL-01"
        write_split(self.root, "sealed_id", [sealed_case], [sealed_truth],
                    {"name": "sealed_id", "source": "test"})
        result = self.validate()
        self.assertFalse(result["ok"])
        self.assertTrue(any(item["code"] == "E_CROSS_SPLIT_ID"
                            for item in result["errors"]))

    def test_cross_split_duplicate_input_is_rejected(self):
        sealed_case = copy.deepcopy(self.data["sealed_id"][0][0])
        sealed_truth = copy.deepcopy(self.data["sealed_id"][1][0])
        sealed_case["input"]["problem"] = "解方程：2x+1=5。"
        write_split(self.root, "sealed_id", [sealed_case], [sealed_truth],
                    {"name": "sealed_id", "source": "test"})
        result = self.validate()
        self.assertFalse(result["ok"])
        self.assertTrue(any(item["code"] == "E_CROSS_SPLIT_INPUT"
                            for item in result["errors"]))

    def test_bench_case_id_in_fresh_split_is_rejected(self):
        sealed_case = copy.deepcopy(self.data["sealed_id"][0][0])
        sealed_truth = copy.deepcopy(self.data["sealed_id"][1][0])
        sealed_case["case_id"] = "MATH-01"
        sealed_truth["case_id"] = "MATH-01"
        write_split(self.root, "sealed_id", [sealed_case], [sealed_truth],
                    {"name": "sealed_id", "source": "test"})
        result = self.validate()
        self.assertFalse(result["ok"])
        self.assertTrue(any(item["code"] == "E_BENCH_OVERLAP"
                            for item in result["errors"]))

    def test_missing_split_is_rejected(self):
        import shutil
        shutil.rmtree(self.root / "ood")
        result = self.validate()
        self.assertFalse(result["ok"])
        self.assertTrue(any(item["code"] == "E_MISSING_SPLIT"
                            for item in result["errors"]))

    def test_split_field_mismatch_is_rejected(self):
        cases = copy.deepcopy(self.data["selection"][0])
        cases[0]["split"] = "development"
        write_split(self.root, "selection", cases,
                    self.data["selection"][1],
                    {"name": "selection", "source": "test"})
        result = self.validate()
        self.assertFalse(result["ok"])
        self.assertTrue(any(item["code"] == "E_BAD_SPLIT"
                            for item in result["errors"]))

    def test_missing_truth_is_rejected(self):
        write_split(self.root, "selection", self.data["selection"][0], [],
                    {"name": "selection", "source": "test"})
        result = self.validate()
        self.assertFalse(result["ok"])
        self.assertTrue(any(item["code"] == "E_MISSING_TRUTH"
                            for item in result["errors"]))

    def test_contaminated_fresh_split_is_rejected(self):
        write_split(self.root, "sealed_id",
                    self.data["sealed_id"][0], self.data["sealed_id"][1],
                    {"name": "sealed_id", "source": "test",
                     "contaminated": True})
        result = self.validate()
        self.assertFalse(result["ok"])
        self.assertTrue(any(item["code"] == "E_CONTAMINATED"
                            for item in result["errors"]))

    def test_duplicate_input_within_split_is_rejected(self):
        cases = copy.deepcopy(self.data["selection"][0])
        duplicate = copy.deepcopy(cases[0])
        duplicate["case_id"] = "SEL-02"
        cases.append(duplicate)
        truths = copy.deepcopy(self.data["selection"][1])
        extra = copy.deepcopy(truths[0])
        extra["case_id"] = "SEL-02"
        truths.append(extra)
        write_split(self.root, "selection", cases, truths,
                    {"name": "selection", "source": "test"})
        result = self.validate()
        self.assertFalse(result["ok"])
        self.assertTrue(any(item["code"] == "E_DUP_INPUT"
                            for item in result["errors"]))


if __name__ == "__main__":
    unittest.main()
