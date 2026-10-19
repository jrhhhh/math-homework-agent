# -*- coding: utf-8 -*-
"""claude adapter 的纯函数测试（不调用 CLI、不花钱）。"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from rsi.adapters import _claude, claude_outer  # noqa: E402


class ClaudeHelpersTests(unittest.TestCase):
    def test_parse_result_skips_warning_lines(self):
        stdout = (
            '[claude-code:unrecognized_model] {"model":"x"}\n'
            + json.dumps({"type": "result", "result": "可以",
                          "total_cost_usd": 0.01}) + "\n"
        )
        payload = _claude.parse_result(stdout)
        self.assertEqual(payload["result"], "可以")

    def test_usage_sums_cache_tokens(self):
        usage = _claude.usage_from_payload({
            "usage": {
                "input_tokens": 10,
                "cache_creation_input_tokens": 5,
                "cache_read_input_tokens": 7,
                "output_tokens": 3,
            },
            "total_cost_usd": 0.02,
            "num_turns": 1,
        })
        self.assertEqual(usage["total_tokens"], 25)
        self.assertEqual(usage["cost_usd"], 0.02)
        self.assertEqual(usage["tool_calls"], 0)

    def test_extract_action_wrapper(self):
        text = 'here is the answer:\n{"action":"clarify","reply":"请补充条件"}\n'
        parsed = _claude.extract_json_object(text)
        self.assertEqual(parsed["action"], "clarify")

    def test_extract_solution_json_is_wrapped_as_solve(self):
        solution = {
            "status": "solved",
            "problem": {"statement": "x"},
            "solution": {"answer": "1"},
        }
        parsed = _claude.extract_json_object(json.dumps(solution))
        self.assertEqual(parsed["action"], "solve")
        self.assertEqual(parsed["output"], solution)

    def test_extract_route_without_action(self):
        parsed = _claude.extract_json_object(
            '{"route_to":"math-error-diagnosis","reply":"请转交"}')
        self.assertEqual(parsed["action"], "route")
        self.assertEqual(parsed["route_to"], "math-error-diagnosis")

    def test_extract_ignores_garbage(self):
        self.assertIsNone(_claude.extract_json_object("没有 JSON"))

    def test_extract_edits_object(self):
        raw = (
            "<<<EDITS\n"
            '{"rationale":"r","edits":[{"path":"SKILL.md",'
            '"find":"a","replace":"b"}]}\n'
            "EDITS>>>"
        )
        parsed = _claude.extract_edits_object(raw)
        self.assertEqual(parsed["rationale"], "r")
        self.assertEqual(parsed["edits"][0]["path"], "SKILL.md")

    def test_prediction_from_text_rejects_bad_solve(self):
        prediction = _claude.prediction_from_text(
            '{"action":"solve","output":"not an object"}')
        self.assertIsNone(prediction["action"])
        self.assertIn("adapter_error", prediction)


class OuterEditTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "references").mkdir()
        (self.root / "SKILL.md").write_text(
            "alpha\nbeta\n", encoding="utf-8")
        (self.root / "references" / "a.md").write_text(
            "reference text\n", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_replace_edit_is_applied(self):
        applied, errors = claude_outer.apply_edits(
            self.root,
            [{"path": "SKILL.md", "find": "beta", "replace": "gamma"}])
        self.assertEqual(errors, [])
        self.assertEqual(applied, ["SKILL.md: replace"])
        self.assertEqual((self.root / "SKILL.md").read_text(encoding="utf-8"),
                         "alpha\ngamma\n")

    def test_frozen_path_is_rejected(self):
        applied, errors = claude_outer.apply_edits(
            self.root,
            [{"path": "bench/x.json", "find": "a", "replace": "b"}])
        self.assertEqual(applied, [])
        self.assertTrue(any("不在可编辑面" in item for item in errors))

    def test_find_miss_is_reported(self):
        applied, errors = claude_outer.apply_edits(
            self.root,
            [{"path": "SKILL.md", "find": "missing", "replace": "x"}])
        self.assertEqual(applied, [])
        self.assertTrue(any("find 未命中" in item for item in errors))

    def test_content_rewrite_is_supported(self):
        applied, errors = claude_outer.apply_edits(
            self.root,
            [{"path": "references/a.md", "content": "new reference\n"}])
        self.assertEqual(errors, [])
        self.assertEqual(applied, ["references/a.md: rewrite"])

    def test_skill_text_includes_references(self):
        text = claude_outer.skill_text(self.root)
        self.assertIn("alpha", text)
        self.assertIn("reference text", text)


if __name__ == "__main__":
    unittest.main()
