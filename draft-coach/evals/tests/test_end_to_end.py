# -*- coding: utf-8 -*-
"""端到端测试：夹具输出 → 重放门脚本 → 打分 → 报告。

用两个真实案例（一个 analyze、一个 refuse）缩小数据集，纯为了跑得快。
**这里跑的是夹具，不是模型输出**，产出方会被标成 `fixture:...`，报告里带警告。
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "make_fixture_predictions.py"
SUITE = ROOT / "evaluate.py"
EVALS = ROOT          # evals/ 里放着 cases.jsonl 与 ground_truth.jsonl

# 只取两条真实案例（一个 analyze、一个 refuse）缩小数据集，纯为跑得快。
SAMPLE_CASE_IDS = {"MATH-01", "BOUND-01"}


def run(*args):
    return subprocess.run([sys.executable, *[str(a) for a in args]],
                          capture_output=True, encoding="utf-8", errors="replace")


class EndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dataset = Path(cls.tmp.name)
        # 从真实数据里筛出两条案例，写成一个临时的 evals 目录
        for filename in ("cases.jsonl", "ground_truth.jsonl"):
            lines = [line for line in (EVALS / filename).read_text(encoding="utf-8").splitlines()
                     if line.strip() and json.loads(line)["case_id"] in SAMPLE_CASE_IDS]
            (cls.dataset / filename).write_text("\n".join(lines) + "\n", encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def make_predictions(self, mode, arm, out_name, lie=False):
        out = Path(self.tmp.name) / out_name
        args = [FIXTURES, "--mode", mode, "--arm", arm, "--dataset", self.dataset, "--out", out]
        if lie:
            args.append("--lie")
        result = run(*args)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return out

    def evaluate(self, predictions, review=None):
        out = Path(self.tmp.name) / "report.json"
        args = [SUITE, "--dataset", self.dataset, "--predictions", predictions,
                "--splits", "development", "--out", out]
        if review:
            args += ["--review", review]
        result = run(*args)
        report = json.loads(out.read_text(encoding="utf-8")) if out.is_file() else None
        return result, report

    def test_oracle_fixture_runs_clean_and_is_labelled_not_a_model_run(self):
        predictions = self.make_predictions("oracle", "skill_gates", "oracle.json")
        result, report = self.evaluate(predictions)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(report["is_model_run"])
        self.assertIn("fixture", report["producer"])
        self.assertEqual(report["severe_failure_count"], 0)
        self.assertEqual(report["missing_predictions"], [])
        self.assertIsNotNone(report["total"]["score"])
        # 只有 A、D 两个子集有案例，其余必须如实标为被剔除且已重新归一化
        self.assertTrue(report["total"]["renormalised"])
        self.assertIn("B_evidence_fidelity", report["total"]["excluded_subsets"])
        self.assertIn("重新归一化", report["total"]["note"])

    def test_oracle_card_passes_both_gates_when_replayed(self):
        predictions = self.make_predictions("oracle", "skill_gates", "oracle.json")
        _result, report = self.evaluate(predictions)
        structure = report["subsets"]["F_output_tool_compliance"]["metric_detail"]["structure_valid"]
        audit = report["subsets"]["F_output_tool_compliance"]["metric_detail"]["audit_clean"]
        self.assertEqual(structure["numerator"], 1)
        self.assertEqual(structure["denominator"], 1)
        self.assertEqual(audit["numerator"], 1, "夹具卡片应当通过 audit --strict")
        # 真实记录了退出码，且与重放一致
        fidelity = report["subsets"]["F_output_tool_compliance"]["metric_detail"]["tool_log_fidelity"]
        self.assertEqual(fidelity["numerator"], 1)

    def test_fabricated_fixture_is_caught_as_s1_and_s5(self):
        predictions = self.make_predictions("fabricated", "skill_gates", "fake.json")
        result, report = self.evaluate(predictions)
        self.assertEqual(result.returncode, 1, "有严重失败时退出码必须是 1")
        codes = {item["code"] for item in report["severe_failures"]}
        self.assertIn("S1", codes, "编造草稿里没有的证据必须被记为 S1")
        self.assertIn("S5", codes, "谎报工具退出码必须被记为 S5")
        fidelity = report["subsets"]["F_output_tool_compliance"]["metric_detail"]["tool_log_fidelity"]
        self.assertLess(fidelity["rate"], 1.0)

    def test_arm_without_gates_has_no_tool_log_metrics(self):
        """skill 组不跑门脚本：与工具记录相关的指标应为不适用，而不是 0 分。"""
        predictions = self.make_predictions("oracle", "skill", "skill.json")
        _result, report = self.evaluate(predictions)
        detail = report["subsets"]["F_output_tool_compliance"]["metric_detail"]
        self.assertIsNone(detail["tool_log_fidelity"]["rate"])
        self.assertIsNone(detail["exit_code_reported"]["rate"])
        self.assertEqual(detail["audit_clean"]["rate"], 1.0)   # 但仍会重放卡片

    def test_review_file_fills_the_model_assisted_layer(self):
        """人工/模型辅助层只从评审文件来；填了才进分母，不填就是未运行。"""
        predictions = self.make_predictions("oracle", "skill_gates", "oracle.json")
        review = Path(self.tmp.name) / "review.json"
        review.write_text(json.dumps({
            "arm": "skill_gates", "layer": "model_assisted", "reviewer": "测试",
            "model_note": "测试用",
            "ratings": [{"case_id": "MATH-01", "metrics": {"fix_correctness": True},
                         "notes": "改法对"}],
        }, ensure_ascii=False), encoding="utf-8")

        _result, without = self.evaluate(predictions)
        _result, with_review = self.evaluate(predictions, review=review)
        self.assertIsNone(without["subsets"]["A_math_error_localization"]["by_layer"]["model_assisted"]["rate"])
        stats = with_review["subsets"]["A_math_error_localization"]["by_layer"]["model_assisted"]
        self.assertEqual(stats["numerator"], 1)
        self.assertEqual(stats["denominator"], 1)

    def test_bad_review_value_is_rejected_with_exit_code_two(self):
        predictions = self.make_predictions("oracle", "skill_gates", "oracle.json")
        review = Path(self.tmp.name) / "bad_review.json"
        review.write_text(json.dumps({
            "arm": "skill_gates", "layer": "human", "reviewer": "测试", "model_note": "x",
            "ratings": [{"case_id": "MATH-01", "metrics": {"fix_correctness": "true"}}],
        }, ensure_ascii=False), encoding="utf-8")
        result, _report = self.evaluate(predictions, review=review)
        self.assertEqual(result.returncode, 2)
        self.assertIn("布尔值", result.stdout)

    def test_unknown_case_in_predictions_is_rejected(self):
        payload = json.loads(self.make_predictions("oracle", "skill_gates", "o.json").read_text(encoding="utf-8"))
        payload["predictions"].append({"case_id": "MATH-777", "response": "", "card": None, "tool_log": []})
        bad = Path(self.tmp.name) / "bad.json"
        bad.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        result, _report = self.evaluate(bad)
        self.assertEqual(result.returncode, 2)
        self.assertIn("MATH-777", result.stdout)

    def test_missing_prediction_is_reported_and_exits_one(self):
        path = self.make_predictions("oracle", "skill_gates", "oracle.json")
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["predictions"] = [p for p in payload["predictions"] if p["case_id"] != "BOUND-01"]
        trimmed = Path(self.tmp.name) / "trimmed.json"
        trimmed.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        result, report = self.evaluate(trimmed)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report["missing_predictions"], ["BOUND-01"])

    def test_markdown_report_is_written(self):
        predictions = self.make_predictions("oracle", "skill_gates", "oracle.json")
        md = Path(self.tmp.name) / "report.md"
        result = run(SUITE, "--dataset", self.dataset, "--predictions", predictions,
                     "--splits", "development", "--markdown", md)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        text = md.read_text(encoding="utf-8")
        self.assertIn("不是模型运行结果", text)
        self.assertIn("重新归一化", text)
        self.assertIn("未运行", text)


class KnownGateFalsePositiveTests(unittest.TestCase):
    """记录一处**已知的、属于技能门脚本的**假阳性，并把它钉住。

    DIM-04 用「方法①/方法②」标同一道题的两条路径。门脚本的 PROBLEM_MARKER_RE
    把带圈序号当题号标记，于是这份**一道题**的草稿被判成「整张纸多题」，
    `audit --strict` 因此把一个完全正确的卡片判为不过。

    这是基准跑出来的真实发现，不是基准的 bug，所以**不改数据集去迁就它**
    （DIM-04 本来就只有一道题，不该加 audit_draft）。这里只断言它没有扩散：
    完美夹具最多只有这一张卡片过不了严格门，且必须正是 DIM-04。
    """

    def test_only_dim_04_fails_the_strict_gate_for_a_perfect_card(self):
        import importlib.util
        sys.path.insert(0, str(ROOT / "engine"))
        import gate_replay
        from cases import load_cases

        spec = importlib.util.spec_from_file_location("fixture_builder", FIXTURES)
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)

        config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
        failures = []
        for case in load_cases(EVALS):
            if case["expected_action"] != "analyze":
                continue
            card = builder.build_oracle_card(case)
            result = gate_replay.replay_card(config, card,
                                             gate_replay.audit_draft_for(case),
                                             case["input"].get("final_solution"))
            if result["audit_strict"]["exit"] != 0:
                failures.append((case["case_id"], result["audit_strict"]["warnings"]))
        self.assertEqual([f[0] for f in failures], ["DIM-04"],
                         "已知假阳性扩散了：%r" % failures)
        self.assertEqual(failures[0][1], ["W_MULTI_PROBLEM_DRAFT"])


if __name__ == "__main__":
    unittest.main()
