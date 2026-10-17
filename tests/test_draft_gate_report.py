# -*- coding: utf-8 -*-
"""draft_gate_report.py 的回归测试。

门层报告只重放已保存回答的退出码：它读 inputs.json 与 skill.json，把每张卡片
重新喂给技能的两道门（draft-coach/scripts/validate_output.py 与 audit_output.py），
记录真实退出码与命中的代码。
这里测的是**报告本身**的形状与退出码，不测任何数学。

用 sys.executable 起子进程：Windows 上 PATH 里的 python3 可能是应用商店占位程序，
会静默退出（同 test_draft_coach.py 的理由）。
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tests/behavior-evaluation/draft_gate_report.py"
EXAMPLES = ROOT / "draft-coach/example"
SAVED = ROOT / "tests/behavior-evaluation/draft-coach-2026-10-15"

# 与 draft-coach/example/high_school_cubic.json 配套的草稿原文。
CUBIC_DRAFT = ("左上角写 x^3-3x 求极值；中间写 f'(x)=3x^2-3；下面写 3x^2=3 → x^2=1 → "
               "x=1（划掉）x=±1；右边写 f(1)=1-3=-2；右下角写 f(-1)=-1+3=2；"
               "底部写 极大值2 极小值-2")


def run_report(directory):
    return subprocess.run([sys.executable, str(SCRIPT), str(directory)],
                          capture_output=True, encoding="utf-8", errors="replace")


def write_case(directory, draft, card, response="占位回答", extra_inputs=None):
    """造一个最小的评测目录：一条输入 + 一条 skill 回答。"""
    directory = Path(directory)
    inputs = [{"id": "X01", "kind": "analysis", "draft": draft, "grade_level": "高中",
               "final_solution": None, "expectation": {}}]
    if extra_inputs:
        inputs[0].update(extra_inputs)
    (directory / "inputs.json").write_text(json.dumps(inputs, ensure_ascii=False),
                                           encoding="utf-8")
    (directory / "skill.json").write_text(
        json.dumps([{"id": "X01", "response": response, "card": card}], ensure_ascii=False),
        encoding="utf-8")
    return directory


class DraftGateReportTests(unittest.TestCase):
    def test_clean_card_passes_both_gates(self):
        card = json.loads((EXAMPLES / "high_school_cubic.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            write_case(tmp, CUBIC_DRAFT, card)
            result = run_report(tmp)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["cards_produced"], 1)
        self.assertEqual(payload["validate_clean"], 1)
        self.assertEqual(payload["audit_strict_clean"], 1)
        self.assertEqual(payload["both_gates_clean"], ["X01"])
        self.assertEqual(payload["gate_failed_cases"], [])

    def test_structural_damage_fails_validate_but_is_still_valid_input(self):
        card = json.loads((EXAMPLES / "high_school_cubic.json").read_text(encoding="utf-8"))
        del card["next_step"]                      # 结构门应当报 E_MISSING_FIELD
        card["top_3_habits"] = []                  # 习惯不足 1 条
        with tempfile.TemporaryDirectory() as tmp:
            write_case(tmp, CUBIC_DRAFT, card)
            result = run_report(tmp)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)  # 有效但不合格
        payload = json.loads(result.stdout)
        case = payload["per_case"][0]
        self.assertEqual(case["card"]["validate"]["exit"], 1)
        self.assertIn("E_MISSING_FIELD", case["card"]["validate"]["errors"])
        self.assertIn("E_HABIT_COUNT", case["card"]["validate"]["errors"])
        self.assertEqual(payload["gate_failed_cases"], ["X01"])
        self.assertFalse(payload["passed"])

    def test_documented_counterexample_card_fails_audit(self):
        """仓库自带的反例卡：结构门退出 0，审计因为越界措辞直接退出 1。"""
        card = json.loads((EXAMPLES / "out_of_scope_label.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            write_case(tmp, CUBIC_DRAFT, card)
            result = run_report(tmp)
        payload = json.loads(result.stdout)
        case = payload["per_case"][0]["card"]
        self.assertEqual(case["validate"]["exit"], 0)
        self.assertEqual(case["audit"]["exit"], 1)          # A 组是 error，不用 --strict 也失败
        self.assertIn("A_LABEL", case["audit"]["errors"])
        self.assertIn("A_PLAN", case["audit"]["errors"])
        self.assertEqual(result.returncode, 1)

    def test_missing_card_is_reported_as_none_and_checks_refusal_wording(self):
        """没产卡片不等于过门：如实记 none，并核对回答里出现了哪条标准话术。"""
        with tempfile.TemporaryDirectory() as tmp:
            standard = subprocess.run(
                [sys.executable, str(ROOT / "draft-coach/scripts/audit_output.py"),
                 "refuse", "--reason", "empty"],
                capture_output=True, encoding="utf-8", errors="replace")
            message = json.loads(standard.stdout)["message"]
            write_case(tmp, "", None, response="这里是我的回复：" + message)
            result = run_report(tmp)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)  # 一张卡都没产出
        payload = json.loads(result.stdout)
        case = payload["per_case"][0]
        self.assertEqual(case["card"], "none")
        self.assertEqual(case["refusal_message_matched"]["skill"], ["empty"])
        self.assertEqual(payload["cards_produced"], 0)

    def test_audit_draft_selects_the_block_for_a_multi_problem_sheet(self):
        """整张草稿纸按块过门：audit_draft 覆盖 draft，否则整张纸会误报多题。"""
        sheet = "第一题：2sin x cos x=sin x → 2cos x=1 → cos x=1/2。第二题：(x-2)(x-3)=0 → x=2 或 x=3。"
        block = "第一题：2sin x cos x=sin x → 2cos x=1 → cos x=1/2。"
        card = json.loads((EXAMPLES / "high_school_cubic.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            write_case(tmp, sheet, card, extra_inputs={"audit_draft": block})
            blocked = json.loads(run_report(tmp).stdout)
            write_case(tmp, sheet, card)          # 不给 audit_draft，就只能拿整张纸审
            whole = json.loads(run_report(tmp).stdout)
        self.assertEqual(blocked["per_case"][0]["audit_draft_source"], "audit_draft")
        self.assertNotIn("W_MULTI_PROBLEM_DRAFT", blocked["per_case"][0]["card"]["audit_strict"]["warnings"])
        self.assertEqual(whole["per_case"][0]["audit_draft_source"], "draft")
        self.assertIn("W_MULTI_PROBLEM_DRAFT", whole["per_case"][0]["card"]["audit_strict"]["warnings"])

    def test_input_errors_use_exit_code_two(self):
        card = json.loads((EXAMPLES / "high_school_cubic.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            # 1) skill.json 缺失
            (Path(tmp) / "inputs.json").write_text(
                json.dumps([{"id": "X01", "draft": "写 x+7=3"}], ensure_ascii=False),
                encoding="utf-8")
            self.assertEqual(run_report(tmp).returncode, 2)
        with tempfile.TemporaryDirectory() as tmp:
            # 2) id 顺序与 inputs.json 不一致
            write_case(tmp, CUBIC_DRAFT, card)
            (Path(tmp) / "skill.json").write_text(
                json.dumps([{"id": "X99", "response": "x", "card": card}], ensure_ascii=False),
                encoding="utf-8")
            self.assertEqual(run_report(tmp).returncode, 2)
        with tempfile.TemporaryDirectory() as tmp:
            # 3) 产出了卡片，却没有可传给 --draft 的草稿
            write_case(tmp, "", card)
            self.assertEqual(run_report(tmp).returncode, 2)


@unittest.skipUnless((SAVED / "inputs.json").is_file() and (SAVED / "skill.json").is_file(),
                     "本次评测材料尚未生成")
class SavedEvaluationIntegrityTests(unittest.TestCase):
    """已保存材料的自洽性：内容会随真实回答变化，这里只断言形状。"""

    def test_ids_align_and_report_runs(self):
        inputs = json.loads((SAVED / "inputs.json").read_text(encoding="utf-8"))
        skill = json.loads((SAVED / "skill.json").read_text(encoding="utf-8"))
        self.assertEqual([row["id"] for row in skill], [row["id"] for row in inputs])
        for row in skill:
            self.assertIn("response", row)
            self.assertIn("card", row)
        result = run_report(SAVED)
        self.assertIn(result.returncode, (0, 1), result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
