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
# 版面卡传给 --draft 的是助手自己的版面描述：只有分块、涂改、图形、行序，没有字符内容。
# 用 ①② 标块是正常写法，不能被 W_MULTI_PROBLEM_DRAFT 当成多个题号。
LAYOUT_DRAFT = ("整张纸分左右两块，中间一条竖线；① 左边一块从上往下一共六行，"
                "第三行后半段被横向划掉，右侧补写了一小段；② 右边只有两行；"
                "整张纸没有图形；行距较密。")


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


def run_clarify(payload):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "questions.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return run_audit("clarify", "--input", str(path))


QUESTIONNAIRE = {
    "message": "这张草稿里有 2 处会改变结论，只需要你补这两个记号，不用重打整页。",
    "questions": [
        {"location": "第二块最后一行右端",
         "question": "你提到那里有个不等号但没写清：是 < 还是 ≤？",
         "candidates": ["<", "≤"],
         "affects": "解集的右端点是否取到；如果和上一行的写法不一致，这里就自相矛盾"},
        {"location": "左边第一行开头",
         "question": "那里有一个记号，写的是什么？",
         "affects": "它决定这一项的正负；读错会让后面几行的结果都跟着变"},
    ],
}


class DraftCoachClarifyTests(unittest.TestCase):
    """clarify 是"不分析时的出口"，不是卡片：它只校验问题单。"""

    def test_valid_questionnaire_is_emitted(self):
        result = run_clarify(QUESTIONNAIRE)
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(payload["action"], "clarify")
        self.assertEqual(payload["message"], QUESTIONNAIRE["message"])
        self.assertEqual(len(payload["questions"]), 2)
        self.assertEqual(payload["errors"], [])
        self.assertTrue(payload["passed"])

    def test_candidates_are_optional(self):
        data = json.loads(json.dumps(QUESTIONNAIRE))
        data["questions"][0].pop("candidates")
        result = run_clarify(data)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_question_count_is_capped(self):
        for count, expected in ((0, 1), (6, 1)):
            with self.subTest(count=count):
                data = json.loads(json.dumps(QUESTIONNAIRE))
                data["questions"] = [
                    {"location": "第 %d 处" % i,
                     "question": "第 %d 处写的是什么？" % i,
                     "affects": "第 %d 条结论会跟着变" % i}
                    for i in range(1, count + 1)]
                result = run_clarify(data)
                self.assertEqual(result.returncode, expected, result.stdout)
                if expected:
                    self.assertIn("E_CLARIFY_COUNT",
                                  [e["code"] for e in json.loads(result.stdout)["errors"]])

    def test_duplicate_questions_are_rejected(self):
        data = json.loads(json.dumps(QUESTIONNAIRE))
        data["questions"][1]["question"] = data["questions"][0]["question"]
        result = run_clarify(data)
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertIn("E_DUPLICATE_QUESTION", [e["code"] for e in payload["errors"]])

    def test_missing_affects_is_rejected(self):
        data = json.loads(json.dumps(QUESTIONNAIRE))
        data["questions"][0].pop("affects")
        result = run_clarify(data)
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertIn("E_MISSING_FIELD", [e["code"] for e in payload["errors"]])

    def test_bad_candidates_are_rejected(self):
        cases = [("one", ["<"]), ("five", ["a", "b", "c", "d", "e"]),
                 ("duplicate", ["<", "<"]), ("not a list", "<")]
        for label, candidates in cases:
            with self.subTest(case=label):
                data = json.loads(json.dumps(QUESTIONNAIRE))
                data["questions"][0]["candidates"] = candidates
                result = run_clarify(data)
                payload = json.loads(result.stdout)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("E_BAD_CANDIDATES", [e["code"] for e in payload["errors"]])

    def test_out_of_scope_wording_is_rejected(self):
        data = json.loads(json.dumps(QUESTIONNAIRE))
        data["message"] = "你基础薄弱，先补知识点漏洞。"
        result = run_clarify(data)
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertIn("A_CAUSE", [e["code"] for e in payload["errors"]])

    def test_documented_example_is_reproducible(self):
        saved = card("clarify_marks.json")
        rebuilt = run_clarify({"message": saved["message"],
                               "questions": saved["questions"]})
        self.assertEqual(rebuilt.returncode, 0, rebuilt.stdout)
        self.assertEqual(json.loads(rebuilt.stdout), saved)

    def test_bad_input_uses_exit_code_two(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text("not JSON", encoding="utf-8")
            result = run_audit("clarify", "--input", str(path))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["error"], "questions file is not valid JSON")
        self.assertNotIn("Traceback", result.stderr)


def run_transcribe(payload):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "candidate.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return run_audit("transcribe", "--input", str(path))


CANDIDATE = {
    "message": "下面是我从照片转写的草稿，共 3 行。请逐行核对：不对的地方直接指出来；"
               "你确认之前我不会用它判断对错。",
    "candidate": "第一行 2x+3=7\n第二行 2x=7+3=10\n第三行 x=5",
    "uncertain": [
        {"location": "第二行", "question": "等号右边是 7+3 还是 7-3？",
         "readings": ["7+3", "7-3"], "affects": "移项是否变号；这会决定 x=5 还是 x=2"},
    ],
}


class DraftCoachTranscribeTests(unittest.TestCase):
    """transcribe 只校验候选稿与问题单；它不产出卡片，也不证明转写准确。"""

    def test_valid_candidate_is_emitted(self):
        result = run_transcribe(CANDIDATE)
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(payload["action"], "transcribe")
        self.assertEqual(payload["candidate"], CANDIDATE["candidate"])
        self.assertEqual(payload["errors"], [])
        self.assertTrue(payload["passed"])

    def test_missing_candidate_is_rejected(self):
        data = {k: v for k, v in CANDIDATE.items() if k != "candidate"}
        result = run_transcribe(data)
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertIn("E_EMPTY_TEXT", [e["code"] for e in payload["errors"]])

    def test_uncertain_is_capped(self):
        data = json.loads(json.dumps(CANDIDATE))
        data["uncertain"] = [
            {"location": "第 %d 处" % i, "question": "第 %d 处写的是什么？" % i,
             "affects": "第 %d 条结论会跟着变" % i} for i in range(1, 7)]
        result = run_transcribe(data)
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertIn("E_UNCERTAIN_COUNT", [e["code"] for e in payload["errors"]])

    def test_candidate_text_is_not_scanned_for_out_of_scope(self):
        # candidate 是引用的学生材料，不是助手的建议；越界规则只管 message 与 uncertain
        data = json.loads(json.dumps(CANDIDATE))
        data["candidate"] = "你基础薄弱，先补知识点漏洞。"
        result = run_transcribe(data)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_machine_readings_are_not_scanned_for_out_of_scope(self):
        # readings 同样是机器读到的学生材料，不是助手措辞
        data = json.loads(json.dumps(CANDIDATE))
        data["uncertain"][0]["readings"] = ["基础薄弱", "知识点漏洞"]
        result = run_transcribe(data)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_transcribe_declares_awaiting_confirmation(self):
        result = run_transcribe(CANDIDATE)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "awaiting_student_confirmation")
        self.assertEqual(payload["confirmation_scope"], "full")

    def test_message_is_scanned_for_out_of_scope(self):
        data = json.loads(json.dumps(CANDIDATE))
        data["message"] = "你基础薄弱，先补知识点漏洞。"
        result = run_transcribe(data)
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertIn("A_CAUSE", [e["code"] for e in payload["errors"]])

    def test_documented_example_is_reproducible(self):
        saved = card("transcribe_candidate.json")
        rebuilt = run_transcribe({"message": saved["message"],
                                  "candidate": saved["candidate"],
                                  "uncertain": saved["uncertain"]})
        self.assertEqual(rebuilt.returncode, 0, rebuilt.stdout)
        self.assertEqual(json.loads(rebuilt.stdout), saved)

    def test_bad_input_uses_exit_code_two(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text("not JSON", encoding="utf-8")
            result = run_audit("transcribe", "--input", str(path))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["error"], "candidate file is not valid JSON")
        self.assertNotIn("Traceback", result.stderr)


class DraftCoachMachineTranscriptionTests(unittest.TestCase):
    """机器转写只有在学生确认后才算证据；卡片必须写明这一点。"""

    def make_card(self, scope):
        data = card("high_school_cubic.json")
        data["draft_source"] = "machine_transcription"
        data["error_check"]["scope"] = scope
        return data

    def run_card(self, data):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "card.json"
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return run_audit("audit", "--card", str(path),
                             "--draft", CUBIC_DRAFT, "--strict")

    def test_confirmed_transcription_passes_strict(self):
        result = self.run_card(self.make_card(
            "机器转写，学生已逐行核对，更正 1 处。核对了求导、解方程、代入三步。"))
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(payload["warnings"], [])

    def test_silent_scope_warns(self):
        result = self.run_card(self.make_card("核对了求导、解方程、代入三步。"))
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertIn("W_TRANSCRIPTION_SCOPE_SILENT",
                      [w["code"] for w in payload["warnings"]])

    def test_mixed_symbol_warning_is_exempt_for_confirmed_transcription(self):
        # 形近记号提醒只针对"学生自己描述的照片"；机器转写已经过学生逐行确认，
        # 确认本身就是回原纸看一眼。再报这条会让不等式题永远过不了 --strict。
        data = self.make_card("机器转写，学生已逐行核对，更正 1 处。")
        data["error_check"]["errors"] = [{
            "location": "中部", "evidence": "草稿写 x≤1", "explanation": "端点写错了。",
            "fix": "改成 x<1。"}]
        result = self.run_card(data)
        payload = json.loads(result.stdout)
        self.assertNotIn("W_MIXED_SYMBOL_EVIDENCE",
                         [w["code"] for w in payload["warnings"]])


class DraftCoachLayoutOnlyAuditTests(unittest.TestCase):
    """版面卡：--draft 是助手自己的版面描述，不能拿它做证据检查。"""

    def test_layout_only_card_passes_strict_gates(self):
        result = run_audit("audit", "--card", str(EXAMPLES / "layout_only_photo.json"),
                           "--draft", LAYOUT_DRAFT, "--strict")
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(payload["errors"], [])
        self.assertEqual(payload["warnings"], [])
        self.assertEqual(payload["analysis_basis"], "layout_only")

    def test_layout_only_card_skips_draft_grounding_checks(self):
        # 版面描述里全是版面词，卡片也不会引用里面的记号；两项检查都必须跳过。
        # ①② 标块也不能被当成多个题号。
        result = run_audit("audit", "--card", str(EXAMPLES / "layout_only_photo.json"),
                           "--draft", LAYOUT_DRAFT, "--strict")
        found = [w["code"] for w in json.loads(result.stdout)["warnings"]]
        for code in ("W_DETACHED_DRAFT", "W_ERROR_NOT_IN_DRAFT",
                     "W_MULTI_PROBLEM_DRAFT"):
            with self.subTest(code=code):
                self.assertNotIn(code, found)

    def test_layout_only_scope_must_state_the_boundary(self):
        data = card("layout_only_photo.json")
        data["error_check"]["scope"] = "本次检查了草稿的版面。"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "card.json"
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            result = run_audit("audit", "--card", str(path),
                               "--draft", LAYOUT_DRAFT, "--strict")
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertIn("W_LAYOUT_ONLY_SCOPE_SILENT",
                      [w["code"] for w in payload["warnings"]])
        # 带标准说法时不该报（示例卡里写的是「内容未经学生确认」「不含…计算错误」）
        clean = run_audit("audit", "--card", str(EXAMPLES / "layout_only_photo.json"),
                          "--draft", LAYOUT_DRAFT, "--strict")
        self.assertNotIn("W_LAYOUT_ONLY_SCOPE_SILENT",
                         [w["code"] for w in json.loads(clean.stdout)["warnings"]])

    def test_missing_analysis_basis_is_treated_as_full(self):
        # 历史卡片没有这个字段；审计对旧卡的判据不能变，严格性只放在结构门。
        data = card("high_school_cubic.json")
        data.pop("analysis_basis")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "card.json"
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            result = run_audit("audit", "--card", str(path), "--draft", "9 8 7 6 5")
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("W_DETACHED_DRAFT", [w["code"] for w in payload["warnings"]])

    def test_layout_only_ignores_utilization_when_solution_given(self):
        # 内容没进卡，利用率本来就无从判断；给了最终解答也不构成漏评
        result = run_audit("audit", "--card", str(EXAMPLES / "layout_only_photo.json"),
                           "--draft", LAYOUT_DRAFT, "--final-solution", "x=5", "--strict")
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("W_UTILIZATION_UNAVAILABLE",
                         [w["code"] for w in payload["warnings"]])


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
