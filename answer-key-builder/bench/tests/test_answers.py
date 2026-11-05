# -*- coding: utf-8 -*-
"""答案检查器的单元测试。"""

import sys
from pathlib import Path
import unittest

BENCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCH))

from engine.answers import check_answer  # noqa: E402


def output(answer, derivation=None):
    return {
        "solution": {
            "answer": answer,
            "conditions": [],
            "derivation": derivation or [],
        },
        "verification": {"checks": []},
    }


class AnswerCheckTests(unittest.TestCase):
    def test_value_set(self):
        spec = {"kind": "value_set", "values": [-1]}
        self.assertTrue(check_answer(spec, output("x=-1"))[0])
        self.assertFalse(check_answer(spec, output("x=1"))[0])

    def test_value_set_multiple_roots(self):
        spec = {"kind": "value_set", "values": [2, 3]}
        self.assertTrue(check_answer(spec, output("x=2 或 x=3"))[0])
        self.assertTrue(check_answer(spec, output("x=3, x=2"))[0])
        self.assertFalse(check_answer(spec, output("x=2"))[0])

    def test_value_set_pm(self):
        spec = {"kind": "value_set", "values": [-3, 3]}
        self.assertTrue(check_answer(spec, output("x=±3"))[0])
        self.assertFalse(check_answer(spec, output("x=3"))[0])

    def test_value_set_four_values(self):
        spec = {"kind": "value_set", "values": [-5, -1, 1, 5]}
        self.assertTrue(check_answer(spec, output("a+b∈{-5,-1,1,5}"))[0])
        self.assertFalse(check_answer(spec, output("a+b=5"))[0])

    def test_interval_set(self):
        spec = {"kind": "interval_set", "intervals": [
            {"lo": 2, "hi": None, "lo_closed": True, "hi_closed": False}]}
        self.assertTrue(check_answer(spec, output("[2,+∞)"))[0])
        self.assertFalse(check_answer(spec, output("(2,+∞)"))[0])

    def test_interval_union(self):
        spec = {"kind": "interval_set", "intervals": [
            {"lo": None, "hi": -1, "lo_closed": False, "hi_closed": True},
            {"lo": 3, "hi": None, "lo_closed": True, "hi_closed": False}]}
        self.assertTrue(check_answer(spec, output("(-∞,-1]∪[3,+∞)"))[0])
        self.assertFalse(check_answer(spec, output("[-1,3]"))[0])

    def test_text_forms(self):
        spec = {"kind": "text_forms", "groups": [["√7", "sqrt(7)"]]}
        self.assertTrue(check_answer(spec, output("BC=√7"))[0])
        self.assertFalse(check_answer(spec, output("BC=7"))[0])

    def test_piecewise(self):
        spec = {"kind": "piecewise", "cases": [
            {"label": "a<0", "tokens": [["x<1/a"], ["x>1"]]},
            {"label": "a=0", "tokens": [["x>1"]]},
            {"label": "a=1", "tokens": [["无解"]]},
        ]}
        good = output("a<0：x<1/a 或 x>1；a=0：x>1；a=1：无解")
        bad = output("a<0：x<1/a 或 x>1；a=0：x>1；a=1：x≠1")
        self.assertTrue(check_answer(spec, good)[0])
        self.assertFalse(check_answer(spec, bad)[0])

    def test_empty_set(self):
        spec = {"kind": "empty_set"}
        self.assertTrue(check_answer(spec, output("无解（空集）"))[0])
        self.assertFalse(check_answer(spec, output("x=0"))[0])


if __name__ == "__main__":
    unittest.main()
