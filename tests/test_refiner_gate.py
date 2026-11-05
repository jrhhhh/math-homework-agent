"""solution-refiner 结构门与措辞门的回归测试。"""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "solution-refiner/solution_card_check.py"
EXAMPLE = ROOT / "solution-refiner/example/correct_card.json"
SOLUTION = "用求根公式：x=(5±√1)/2，所以 x1=3，x2=2。"
PROBLEM = "求 x²-5x+6=0 的根。"


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, encoding="utf-8", errors="replace")


def card():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def with_card(data, *args):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "card.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return run(*[arg.replace("{card}", str(path)) for arg in args])


class RefinerGateTests(unittest.TestCase):
    def test_fewer_than_three_real_directions_is_allowed_with_warning(self):
        data = card()
        data["optimization_opportunities"] = data["optimization_opportunities"][:2]
        result = with_card(data, "validate", "--card", "{card}")
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(payload["errors"], [])
        self.assertIn("W_FEWER_DIRECTIONS", [w["code"] for w in payload["warnings"]])

    def test_more_than_three_directions_is_rejected(self):
        data = card()
        extra = copy.deepcopy(data["optimization_opportunities"][0])
        extra["direction"] = "更优雅表达"
        extra["exposed_gap"] = "本解答尚未展示更统一的数学表达。"
        data["optimization_opportunities"].append(extra)
        result = with_card(data, "validate", "--card", "{card}")
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("E_OPP_COUNT", [e["code"] for e in payload["errors"]])

    def test_next_question_wording_is_not_a_variant_problem(self):
        data = card()
        data["optimization_opportunities"][0]["training_suggestion"] = (
            "下一道题先把两种方法各写一遍，再比较关键计算。")
        result = with_card(data, "audit", "--card", "{card}",
                           "--solution", SOLUTION, "--problem", PROBLEM, "--strict")
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("A_VARIANT", [e["code"] for e in payload["errors"]])


if __name__ == "__main__":
    unittest.main()
