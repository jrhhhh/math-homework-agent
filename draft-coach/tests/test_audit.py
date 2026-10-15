"""draft-coach 边界审计（audit）与 refuse 的回归测试。

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
AUDIT = ROOT / "draft-coach/scripts/audit_output.py"
EXAMPLES = ROOT / "draft-coach/example"

CUBIC_DRAFT = ("左上角写 x^3-3x 求极值；中间写 f'(x)=3x^2-3；下面写 3x^2=3 → x^2=1 → "
               "x=1（划掉）x=±1；右边写 f(1)=1-3=-2；右下角写 f(-1)=-1+3=2；"
               "底部写 极大值2 极小值-2")
SUBSTITUTION_DRAFT = ("解 2x+3y=12, x-y=1。写了代入法：由 x-y=1 得 x=y+1，代入得 "
                      "2(y+1)+3y=12，然后划掉一大段，重新写 2y+2+3y=12 → 5y=10 → y=2 → x=3")


def run_validate(*args):
    # 门脚本把 stdout 重配成 UTF-8，而 Windows 的默认 locale 是 GBK：
    # 不显式指定 encoding，读取端会拿 GBK 解 UTF-8 而炸掉。
    return subprocess.run([sys.executable, str(VALIDATE), *args],
                          capture_output=True, encoding="utf-8", errors="replace")


def run_audit(*args):
    # 同上：显式 encoding 才不会在 GBK 默认 locale 上炸掉。
    return subprocess.run([sys.executable, str(AUDIT), *args],
                          capture_output=True, encoding="utf-8", errors="replace")


def card(name):
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def codes(payload):
    return [item["code"] for item in payload.get("errors", [])]


class DraftCoachAuditTests(unittest.TestCase):
    def test_process_vocabulary_and_hedged_risk_are_legal(self):
        # 跳步 / 涂改 / 划掉 / 漏根 是本技能的核心词汇；"若…可能漏根"是假设句，不是判错。
        result = run_audit("audit", "--card", str(EXAMPLES / "high_school_cubic.json"),
                           "--draft", CUBIC_DRAFT, "--strict")
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(payload["errors"], [])
        self.assertEqual(payload["warnings"], [])

    def test_fabricated_card_passes_structure_but_fails_boundary(self):
        path = EXAMPLES / "fabricated_error.json"
        # 结构门放过它，正说明结构门不查越界、也不查那条"错误"是不是真的
        self.assertEqual(run_validate("validate", "--card", str(path)).returncode, 0)

        result = run_audit("audit", "--card", str(path), "--draft", CUBIC_DRAFT)
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
            result = run_audit("audit", "--card", str(path), "--draft", CUBIC_DRAFT)
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
            lenient = run_audit("audit", "--card", str(path), "--draft", CUBIC_DRAFT)
            strict = run_audit("audit", "--card", str(path), "--draft", CUBIC_DRAFT, "--strict")
        self.assertIn("W_RISK_UNHEDGED",
                      [w["code"] for w in json.loads(lenient.stdout)["warnings"]])
        self.assertEqual(lenient.returncode, 0)
        self.assertEqual(strict.returncode, 1)

    def test_card_that_ignores_the_draft_warns(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "card.json"
            path.write_text(json.dumps(card("high_school_cubic.json"), ensure_ascii=False),
                            encoding="utf-8")
            result = run_audit("audit", "--card", str(path),
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
            result = run_audit("audit", "--card", str(path), "--draft",
                               "第一题：左上角 x^3-3x 求极值，下面 3x^2=3 → x^2=1 → x=±1；"
                               "第二题：右边解 2x+3y=12，划掉一段后 5y=10 → y=2")
        payload = json.loads(result.stdout)
        self.assertIn("W_MULTI_PROBLEM_DRAFT", [w["code"] for w in payload["warnings"]])
        marker = [w for w in payload["warnings"] if w["code"] == "W_MULTI_PROBLEM_DRAFT"][0]
        self.assertEqual(marker["markers"], ["第一题", "第二题"])

    def test_ordinary_draft_is_not_flagged_as_multi_problem(self):
        # f(1)=-2 这类函数记号里也有括号数字，不能当成题号
        result = run_audit("audit", "--card", str(EXAMPLES / "high_school_cubic.json"),
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
                return run_audit("audit", "--card", str(path), "--draft", CUBIC_DRAFT)

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
            result = run_audit("audit", "--card", str(path), "--draft", CUBIC_DRAFT,
                               "--final-solution", "极大值 2，极小值 -2。")
        self.assertIn("W_UTILIZATION_UNAVAILABLE",
                      [w["code"] for w in json.loads(result.stdout)["warnings"]])

    def test_grade_mismatch_flags_metacognitive_wording(self):
        data = card("junior_high_substitution.json")
        data["dimensions"]["trial_and_error"]["observation"] = "本份草稿尚未展示方法比较。"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "card.json"
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            result = run_audit("audit", "--card", str(path), "--draft", SUBSTITUTION_DRAFT)
        self.assertIn("W_GRADE_MISMATCH",
                      [w["code"] for w in json.loads(result.stdout)["warnings"]])

    def test_declining_to_score_is_not_a_scoring_violation(self):
        # 学生要"按百分制打个分"，答案答"这一项我没有打分"是在**拒绝**越界。
        # A_SCORE 只看字面必然误报，所以命中措辞紧前面的否定词要豁免。
        def with_next_step(text):
            data = card("high_school_cubic.json")
            data["next_step"] = text
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "card.json"
                path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                return run_audit("audit", "--card", str(path), "--draft", CUBIC_DRAFT)

        declined = with_next_step("这道题我没有打分，也不给分数，下一道题只落笔不跳步。")
        self.assertEqual(declined.returncode, 0, declined.stdout)
        self.assertEqual(json.loads(declined.stdout)["errors"], [])

        # 真的主动评分仍然要被拦下——豁免只针对否定句，不是把 A_SCORE 关掉
        actual = with_next_step("这次给你扣分，满分是 10 分。")
        self.assertEqual(actual.returncode, 1)
        self.assertIn("A_SCORE", codes(json.loads(actual.stdout)))

    def test_value_only_in_fix_is_not_unfounded_evidence(self):
        # 一条错误的证据里带着"应改成"的新数值（草稿上没有 4），那不算查无此据：
        # 同一个错误条目的 fix 里已经写了这个值，它是答案给出的**期望值**，
        # 不是对草稿的引述断言。这条证据故意只含一个记号，好把机制单独隔出来测。
        def with_fix(fix_text):
            data = card("high_school_cubic.json")
            data["error_check"]["errors"] = [{
                "location": "第四行",
                "evidence": "第四行写成 4",
                "explanation": "这里少了一个根。",
                "fix": fix_text,
            }]
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "card.json"
                path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                return run_audit("audit", "--card", str(path), "--draft", CUBIC_DRAFT)

        explained = json.loads(with_fix("第四行改成 x=4。").stdout)
        self.assertNotIn("W_ERROR_NOT_IN_DRAFT",
                         [w["code"] for w in explained["warnings"]])

        # fix 里也没有 4 时，本门照旧把它当成"草稿上找不到"的候选记号
        unexplained = json.loads(with_fix("这一行重算一遍。").stdout)
        marker = [w for w in unexplained["warnings"] if w["code"] == "W_ERROR_NOT_IN_DRAFT"]
        self.assertEqual(len(marker), 1)
        self.assertEqual(marker[0]["candidates"], ["4"])

    def test_ambiguous_symbol_evidence_warns_only_for_image_drafts(self):
        # ≤ 与 < 在手写里近乎同形：从图片读来的这类记号不许单独支撑一条错误，
        # 门对图片来源的卡片报 W_MIXED_SYMBOL_EVIDENCE 提醒；学生打字来的草稿不提醒。
        def run_with(source):
            data = card("high_school_cubic.json")
            data["draft_source"] = source
            data["error_check"]["errors"] = [{
                "location": "第四行",
                "evidence": "第四行写 √3/2 < sin(A + π/6) ≤ 1",
                "explanation": "端点的开闭与上一行对不上。",
                "fix": "把端点符号改成与上一行一致。",
            }]
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "card.json"
                path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                return json.loads(run_audit("audit", "--card", str(path),
                                            "--draft", CUBIC_DRAFT).stdout)

        photo = run_with("image_description")
        marker = [w for w in photo["warnings"] if w["code"] == "W_MIXED_SYMBOL_EVIDENCE"]
        self.assertEqual(len(marker), 1, photo["warnings"])
        self.assertEqual(marker[0]["symbols"], ["<", "≤"])

        typed = run_with("text_reconstruction")
        self.assertNotIn("W_MIXED_SYMBOL_EVIDENCE",
                         [w["code"] for w in typed["warnings"]])

    def test_audit_requires_a_draft(self):
        result = run_audit("audit", "--card", str(EXAMPLES / "high_school_cubic.json"))
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)

    def test_audit_bad_card_uses_exit_code_two(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text("not JSON", encoding="utf-8")
            result = run_audit("audit", "--card", str(path), "--draft", CUBIC_DRAFT)
        self.assertEqual(result.returncode, 2)


class DraftCoachRefuseTests(unittest.TestCase):
    def test_refuse_exit_codes_and_payload_shape(self):
        # 2 = 草稿本身不能当证据；1 = 草稿有效，但这个问题不归本技能管
        for reason, error, expected in [("empty", "无草稿", 2),
                                        ("unreadable", "草稿无法识别", 2),
                                        ("out_of_scope", "超出范围", 1)]:
            with self.subTest(reason=reason):
                result = run_audit("refuse", "--reason", reason)
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
                result = run_audit("refuse", "--reason", reason)
                self.assertEqual(json.loads(result.stdout),
                                 json.loads((EXAMPLES / filename).read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
