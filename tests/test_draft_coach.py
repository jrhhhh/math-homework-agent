"""draft-coach 的门回归测试。

注意：仓库里 test_handoff.py 用字面量 "python3" 起子进程，而本机 PATH 上的 python3
是应用商店占位程序（静默退出）。这里改用 sys.executable，跑测试的解释器就是子进程
用的解释器，测试因此可移植。
"""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "draft-coach/draft_coach_check.py"
EXAMPLES = ROOT / "draft-coach/example"

CUBIC_DRAFT = ("左上角写 x^3-3x 求极值；中间写 f'(x)=3x^2-3；下面写 3x^2=3 → x^2=1 → "
               "x=1（划掉）x=±1；右边写 f(1)=1-3=-2；右下角写 f(-1)=-1+3=2；"
               "底部写 极大值2 极小值-2")
SUBSTITUTION_DRAFT = ("解 2x+3y=12, x-y=1。写了代入法：由 x-y=1 得 x=y+1，代入得 "
                      "2(y+1)+3y=12，然后划掉一大段，重新写 2y+2+3y=12 → 5y=10 → y=2 → x=3")


def run(*args):
    # 门脚本把 stdout 重配成 UTF-8，而 Windows 的默认 locale 是 GBK：
    # 不显式指定 encoding，读取端会拿 GBK 解 UTF-8 而炸掉。
    return subprocess.run([sys.executable, str(CHECKER), *args],
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
        result = run("validate", "--card", str(path))
        return result.returncode, json.loads(result.stdout) if result.stdout else {}


def codes(payload):
    return [item["code"] for item in payload.get("errors", [])]


class DraftCoachValidateTests(unittest.TestCase):
    def test_real_example_cards_pass_clean(self):
        for name in ("high_school_cubic.json", "junior_high_substitution.json"):
            with self.subTest(card=name):
                result = run("validate", "--card", str(EXAMPLES / name))
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
            ("只有两条习惯", lambda d: d.update(top_3_habits=d["top_3_habits"][:2]),
             "E_HABIT_COUNT"),
            ("多余的顶层字段", lambda d: d.update(process_status="valid"),
             "E_EXTRA_FIELD"),
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
            ("缺少错误清单", lambda d: d.pop("error_check"),
             "E_MISSING_FIELD"),
            ("错误清单缺 errors", lambda d: d["error_check"].pop("errors"),
             "E_MISSING_FIELD"),
            ("错误清单范围为空", lambda d: d["error_check"].update(scope=" "),
             "E_EMPTY_TEXT"),
            ("errors 不是数组", lambda d: d["error_check"].update(errors={}),
             "E_BAD_ERROR_LIST"),
            ("错误条目缺 fix", lambda d: d["error_check"].update(errors=[
                {"location": "中部", "evidence": "草稿写 3x²=3", "explanation": "此处存疑"}]),
             "E_MISSING_FIELD"),
        ]
        for label, mutate, expected in cases:
            with self.subTest(case=label):
                code, payload = validate(mutate)
                self.assertEqual(code, 1, payload)
                self.assertIn(expected, codes(payload))

    def test_unavailable_score_only_allowed_for_draft_utilization(self):
        # 「不适用」是给"没有最终解答"留的口子，不能挪到别的维度
        code, payload = validate(
            lambda d: d["dimensions"]["organization"].update(score="不适用"))
        self.assertEqual(code, 1)
        self.assertIn("E_BAD_SCORE", codes(payload))

        code, payload = validate(
            lambda d: d["dimensions"]["draft_to_solution"].update(score="不适用"))
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
                    result = run("validate", "--card", str(path))
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(json.loads(result.stdout)["error"], expected)
                    self.assertNotIn("Traceback", result.stderr)


class DraftCoachAuditTests(unittest.TestCase):
    def test_process_vocabulary_and_hedged_risk_are_legal(self):
        # 跳步 / 涂改 / 划掉 / 漏根 是本技能的核心词汇；"若…可能漏根"是假设句，不是判错。
        result = run("audit", "--card", str(EXAMPLES / "high_school_cubic.json"),
                     "--draft", CUBIC_DRAFT, "--strict")
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(payload["errors"], [])
        self.assertEqual(payload["warnings"], [])

    def test_fabricated_card_passes_structure_but_fails_boundary(self):
        path = EXAMPLES / "fabricated_error.json"
        # 结构门放过它，正说明结构门不查越界、也不查那条"错误"是不是真的
        self.assertEqual(run("validate", "--card", str(path)).returncode, 0)

        result = run("audit", "--card", str(path), "--draft", CUBIC_DRAFT)
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(sorted(codes(payload)), ["A_LABEL", "A_PLAN"])
        warning_codes = [w["code"] for w in payload["warnings"]]
        self.assertIn("W_ERROR_NOT_IN_DRAFT", warning_codes)
        self.assertIn("W_POSITIVE_ABSENT", warning_codes)
        # 编造的那条错误引用了 48/4/12，草稿里一个都没有
        marker = [w for w in payload["warnings"] if w["code"] == "W_ERROR_NOT_IN_DRAFT"][0]
        self.assertEqual(marker["candidates"], ["48", "4", "12"])
        self.assertNotIn("Traceback", result.stderr)

    def test_judging_correctness_is_now_in_scope(self):
        # 2026-10-11 重新定位：查计算错误是本职，"这一步算错了""正确答案是"不再越界
        data = card("high_school_cubic.json")
        data["error_check"]["errors"] = [{
            "location": "草稿下面",
            "evidence": "草稿写 3x²=3 → x²=1 → x=±1",
            "explanation": "这一步算错了，正确答案是 x=±1 两个根，草稿只留下一个。",
            "fix": "在 x²=1 后面补一行 x=±1。",
        }]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "card.json"
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            result = run("audit", "--card", str(path), "--draft", CUBIC_DRAFT)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(json.loads(result.stdout)["errors"], [])

    def test_unhedged_risk_warns(self):
        # 风险句要说"若…可能…"。写成已经发生的结论就会被拦下。
        # 注意"下次还会错"不算：这里的"会"是未来预测，审计针对的是判决口吻。
        data = card("high_school_cubic.json")
        data["dimensions"]["correction_pattern"]["risk"] = \
            "涂改处没有标注，回头复盘时看不出哪里出了错。"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "card.json"
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            lenient = run("audit", "--card", str(path), "--draft", CUBIC_DRAFT)
            strict = run("audit", "--card", str(path), "--draft", CUBIC_DRAFT, "--strict")
        self.assertIn("W_RISK_UNHEDGED",
                      [w["code"] for w in json.loads(lenient.stdout)["warnings"]])
        self.assertEqual(lenient.returncode, 0)
        self.assertEqual(strict.returncode, 1)

    def test_card_that_ignores_the_draft_warns(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "card.json"
            path.write_text(json.dumps(card("high_school_cubic.json"), ensure_ascii=False),
                            encoding="utf-8")
            result = run("audit", "--card", str(path),
                         "--draft", "计算 1234+5678 得 6912，其余没有写。")
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0)
        self.assertIn("W_DETACHED_DRAFT", [w["code"] for w in payload["warnings"]])

    def test_whole_sheet_looks_like_multiple_problems(self):
        # 一整张草稿纸：分块归属是模型和学生的活，脚本只负责提醒"这看着不止一道题"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "card.json"
            path.write_text(json.dumps(card("high_school_cubic.json"), ensure_ascii=False),
                            encoding="utf-8")
            result = run("audit", "--card", str(path), "--draft",
                         "第一题：左上角 x^3-3x 求极值，下面 3x^2=3 → x^2=1 → x=±1；"
                         "第二题：右边解 2x+3y=12，划掉一段后 5y=10 → y=2")
        payload = json.loads(result.stdout)
        self.assertIn("W_MULTI_PROBLEM_DRAFT", [w["code"] for w in payload["warnings"]])
        marker = [w for w in payload["warnings"] if w["code"] == "W_MULTI_PROBLEM_DRAFT"][0]
        self.assertEqual(marker["markers"], ["第一题", "第二题"])

    def test_ordinary_draft_is_not_flagged_as_multi_problem(self):
        # f(1)=-2 这类函数记号里也有括号数字，不能当成题号
        result = run("audit", "--card", str(EXAMPLES / "high_school_cubic.json"),
                     "--draft", CUBIC_DRAFT)
        self.assertNotIn("W_MULTI_PROBLEM_DRAFT",
                         [w["code"] for w in json.loads(result.stdout)["warnings"]])

    def test_describing_a_full_process_is_not_giving_one(self):
        # "定位不到某一道题的完整过程"是在描述草稿，不是给出解答——不能误判
        def with_risk(text):
            data = card("high_school_cubic.json")
            data["dimensions"]["organization"]["risk"] = text
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "card.json"
                path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                return run("audit", "--card", str(path), "--draft", CUBIC_DRAFT)

        ok = with_risk("回头核对时定位不到某一道题的完整过程，只能从头逐行重读。")
        self.assertEqual(ok.returncode, 0, ok.stdout)

        bad = with_risk("下面是完整解法：由余弦定理得 c=2。")
        self.assertEqual(bad.returncode, 1)
        self.assertIn("A_SOLUTION", codes(json.loads(bad.stdout)))

    def test_utilization_cannot_be_unavailable_when_solution_given(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "card.json"
            data = card("high_school_cubic.json")
            data["dimensions"]["draft_to_solution"]["score"] = "不适用"
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            result = run("audit", "--card", str(path), "--draft", CUBIC_DRAFT,
                         "--final-solution", "极大值 2，极小值 -2。")
        self.assertIn("W_UTILIZATION_UNAVAILABLE",
                      [w["code"] for w in json.loads(result.stdout)["warnings"]])

    def test_grade_mismatch_flags_metacognitive_wording(self):
        data = card("junior_high_substitution.json")
        data["dimensions"]["trial_and_error"]["observation"] = "本份草稿尚未展示方法比较。"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "card.json"
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            result = run("audit", "--card", str(path), "--draft", SUBSTITUTION_DRAFT)
        self.assertIn("W_GRADE_MISMATCH",
                      [w["code"] for w in json.loads(result.stdout)["warnings"]])

    def test_audit_requires_a_draft(self):
        result = run("audit", "--card", str(EXAMPLES / "high_school_cubic.json"))
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)

    def test_audit_bad_card_uses_exit_code_two(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text("not JSON", encoding="utf-8")
            result = run("audit", "--card", str(path), "--draft", CUBIC_DRAFT)
        self.assertEqual(result.returncode, 2)


class DraftCoachOtherCommandTests(unittest.TestCase):
    def test_refuse_exit_codes_and_payload_shape(self):
        # 2 = 草稿本身不能当证据；1 = 草稿有效，但这个问题不归本技能管
        for reason, error, expected in [("empty", "无草稿", 2),
                                        ("unreadable", "草稿无法识别", 2),
                                        ("out_of_scope", "超出范围", 1)]:
            with self.subTest(reason=reason):
                result = run("refuse", "--reason", reason)
                payload = json.loads(result.stdout)
                self.assertEqual(result.returncode, expected)
                self.assertEqual(payload["action"], "refuse")
                self.assertEqual(payload["error"], error)
                self.assertTrue(payload["message"])

    def test_documented_refuse_examples_are_reproducible(self):
        for reason, filename in [("empty", "refuse_empty.json"),
                                 ("unreadable", "refuse_unreadable.json"),
                                 ("out_of_scope", "refuse_out_of_scope.json")]:
            with self.subTest(reason=reason):
                result = run("refuse", "--reason", reason)
                self.assertEqual(json.loads(result.stdout),
                                 json.loads((EXAMPLES / filename).read_text(encoding="utf-8")))

    def test_hint_declares_itself_non_authoritative(self):
        result = run("hint", "--draft", CUBIC_DRAFT, "--grade-level", "高中")
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(payload["authority"], "heuristic-hint-only")
        self.assertEqual([d["key"] for d in payload["dimensions"]],
                         ["organization", "skipping", "correction_pattern",
                          "trial_and_error", "graphic_use", "draft_to_solution"])
        self.assertEqual([g["grade"] for g in payload["grade_menu"]],
                         ["小学", "初中", "高中", "大学"])

    def test_hint_rejects_bad_grade_and_empty_draft(self):
        self.assertEqual(run("hint", "--draft", "x=1", "--grade-level", "研究生").returncode, 2)
        self.assertEqual(run("hint", "--draft", "   ").returncode, 2)


if __name__ == "__main__":
    unittest.main()
