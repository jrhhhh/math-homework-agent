"""draft-coach 结构门（validate）与 hint 的回归测试。

注意：仓库里 test_handoff.py 用字面量 "python3" 起子进程，而本机 PATH 上的 python3
是应用商店占位程序（静默退出）。这里改用 sys.executable，跑测试的解释器就是子进程
用的解释器，测试因此可移植。
"""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
VALIDATE = ROOT / "draft-coach/scripts/validate_output.py"
EXAMPLES = ROOT / "draft-coach/example"

CUBIC_DRAFT = ("左上角写 x^3-3x 求极值；中间写 f'(x)=3x^2-3；下面写 3x^2=3 → x^2=1 → "
               "x=1（划掉）x=±1；右边写 f(1)=1-3=-2；右下角写 f(-1)=-1+3=2；"
               "底部写 极大值2 极小值-2")


def run_validate(*args):
    # 门脚本把 stdout 重配成 UTF-8，而 Windows 的默认 locale 是 GBK：
    # 不显式指定 encoding，读取端会拿 GBK 解 UTF-8 而炸掉。
    return subprocess.run([sys.executable, str(VALIDATE), *args],
                          capture_output=True, encoding="utf-8", errors="replace")


def card(name):
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def validate(mutate=None):
    """把示例卡改坏一点，写到临时文件里跑结构门，返回 (退出码, 输出)。"""
    data = card("high_school_cubic.json")
    if mutate:
        mutate(data)
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "card.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        result = run_validate("validate", "--card", str(path))
        return result.returncode, json.loads(result.stdout) if result.stdout else {}


def codes(payload):
    return [item["code"] for item in payload.get("errors", [])]


class DraftCoachValidateTests(unittest.TestCase):
    def test_real_example_cards_pass_clean(self):
        for name in ("high_school_cubic.json", "junior_high_substitution.json",
                     "junior_high_transposition.json", "layout_habits.json"):
            with self.subTest(card=name):
                result = run_validate("validate", "--card", str(EXAMPLES / name))
                payload = json.loads(result.stdout)
                self.assertEqual(result.returncode, 0, result.stdout)
                self.assertEqual(payload["errors"], [])
                self.assertEqual(payload["warnings"], [])
                self.assertTrue(payload["passed"])

    def test_structural_damage_is_rejected(self):
        cases = [
            ("缺少一个维度", lambda d: d["dimensions"].pop("graphic_use"),
             "E_MISSING_DIMENSION"),
            ("评分越界", lambda d: d["dimensions"]["skipping"].update(score="很好"),
             "E_BAD_SCORE"),
            ("没有习惯", lambda d: d.update(top_3_habits=[]),
             "E_HABIT_COUNT"),
            ("超过三条习惯", lambda d: d.update(
                top_3_habits=d["top_3_habits"] + [dict(d["top_3_habits"][0],
                                                      habit="第四条不同的习惯")]),
             "E_HABIT_COUNT"),
            ("多余的顶层字段", lambda d: d.update(process_status="valid"),
             "E_EXTRA_FIELD"),
            ("缺少 scope", lambda d: d.pop("scope"),
             "E_MISSING_FIELD"),
            ("scope 为空", lambda d: d.update(scope="  "),
             "E_EMPTY_TEXT"),
            ("缺少 next_step", lambda d: d.pop("next_step"),
             "E_MISSING_FIELD"),
            ("学段非法", lambda d: d.update(grade_level="研究生"),
             "E_BAD_GRADE"),
            ("草稿来源非法", lambda d: d.update(draft_source="口头转述"),
             "E_BAD_SOURCE"),
            ("证据为空", lambda d: d["dimensions"]["organization"].update(evidence="  "),
             "E_EMPTY_TEXT"),
            ("习惯字段缺失", lambda d: d["top_3_habits"][0].pop("impact"),
             "E_MISSING_FIELD"),
            ("习惯重复", lambda d: d["top_3_habits"][1].update(
                habit=d["top_3_habits"][0]["habit"]),
             "E_DUPLICATE_HABIT"),
            ("混入错误清单", lambda d: d.update(error_check={
                "scope": "x", "errors": []}),
             "E_EXTRA_FIELD"),
        ]
        for label, mutate, expected in cases:
            with self.subTest(case=label):
                code, payload = validate(mutate)
                self.assertEqual(code, 1, payload)
                self.assertIn(expected, codes(payload))

    def test_unavailable_score_allowed_with_reason(self):
        # 观察不足时任一维度都可以标「不适用」，但 observation 要写明原因。
        code, payload = validate(lambda d: d["dimensions"]["organization"].update(
            score="不适用", observation="草稿太短，无法判断有没有分区。"))
        self.assertEqual(code, 0, payload)
        self.assertNotIn("W_UNAVAILABLE_WITHOUT_REASON",
                         [w["code"] for w in payload["warnings"]])

        code, payload = validate(lambda d: d["dimensions"]["organization"].update(
            score="不适用", observation="左上角写题目，过程在中间。"))
        self.assertEqual(code, 0, payload)
        self.assertIn("W_UNAVAILABLE_WITHOUT_REASON",
                      [w["code"] for w in payload["warnings"]])

        code, payload = validate(
            lambda d: d["dimensions"]["draft_to_solution"].update(score="不适用"))
        self.assertEqual(code, 0, payload)

    def test_one_to_three_habits_are_structurally_allowed(self):
        for count in (1, 2, 3):
            with self.subTest(count=count):
                code, payload = validate(
                    lambda d: d.update(top_3_habits=d["top_3_habits"][:count]))
                self.assertEqual(code, 0, payload)

    def test_positive_field_is_correction_pattern_only(self):
        code, payload = validate(lambda d: d["dimensions"]["organization"].update(
            positive="分区很自觉。"))
        self.assertEqual(code, 1)
        self.assertIn("E_EXTRA_FIELD", codes(payload))

        code, payload = validate(lambda d: d["dimensions"]["correction_pattern"].update(
            positive="划掉后立刻补回 ±，说明回头核对过。"))
        self.assertEqual(code, 0, payload)

    def test_extra_dimension_name_is_rejected(self):
        code, payload = validate(lambda d: d["dimensions"].update(
            metacognition={"score": "高", "observation": "a", "evidence": "bbbbbb",
                           "risk": "无。"}))
        self.assertEqual(code, 1)
        self.assertIn("E_EXTRA_DIMENSION", codes(payload))

    def test_input_errors_use_exit_code_two(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            bad_json = directory / "bad.json"
            bad_json.write_text("not JSON", encoding="utf-8")
            bad_encoding = directory / "bad-encoding.json"
            bad_encoding.write_bytes(b"\xff\xfe")
            not_object = directory / "array.json"
            not_object.write_text("[1, 2, 3]", encoding="utf-8")
            cases = [(directory / "missing.json", "card file not found"),
                     (bad_json, "card file is not valid JSON"),
                     (bad_encoding, "card file is not valid UTF-8"),
                     (not_object, "card must be a JSON object")]
            for path, expected in cases:
                with self.subTest(path=path.name):
                    result = run_validate("validate", "--card", str(path))
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(json.loads(result.stdout)["error"], expected)
                    self.assertNotIn("Traceback", result.stderr)


class DraftCoachHintTests(unittest.TestCase):
    def test_hint_declares_itself_non_authoritative(self):
        result = run_validate("hint", "--draft", CUBIC_DRAFT, "--grade-level", "高中")
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(payload["authority"], "heuristic-hint-only")
        self.assertEqual([d["key"] for d in payload["dimensions"]],
                         ["organization", "skipping", "correction_pattern",
                          "trial_and_error", "graphic_use", "draft_to_solution"])
        self.assertEqual([g["grade"] for g in payload["grade_menu"]],
                         ["小学", "初中", "高中", "大学"])

    def test_hint_detects_math_layout_cues(self):
        draft = ("分类讨论：① 当 x>0；② 当 x<0。几何图画了图，辅助线没标顶点；"
                 "最后没有留检验区。")
        result = run_validate("hint", "--draft", draft, "--grade-level", "高中")
        payload = json.loads(result.stdout)
        keys = {item["dimension"] for item in payload["detected_signals"]}
        self.assertIn("trial_and_error", keys)
        self.assertIn("graphic_use", keys)
        self.assertIn("draft_to_solution", keys)

    def test_hint_rejects_bad_grade_and_empty_draft(self):
        self.assertEqual(run_validate("hint", "--draft", "x=1", "--grade-level", "研究生").returncode, 2)
        self.assertEqual(run_validate("hint", "--draft", "   ").returncode, 2)


if __name__ == "__main__":
    unittest.main()
