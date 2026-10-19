# -*- coding: utf-8 -*-
"""rsi.loop 的端到端回归测试（夹具驱动，不调用模型）。"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "math-solver" / "bench"))

from engine.data import load_jsonl  # noqa: E402
from make_fixture_predictions import build_bad, build_oracle  # noqa: E402
from rsi import loop, outer, runner  # noqa: E402

BENCH = REPO / "math-solver" / "bench"
CASE_IDS = ("MATH-01", "MATH-02")


def make_skill(root: Path) -> None:
    (root / "references").mkdir(parents=True)
    (root / "bench").mkdir()
    (root / "scripts").mkdir()
    (root / "tests").mkdir()
    (root / "example").mkdir()
    (root / "SKILL.md").write_text("line one\nline two\n", encoding="utf-8")
    (root / "references" / "a.md").write_text("reference\n", encoding="utf-8")
    (root / "bench" / "cases.jsonl").write_text("{}\n", encoding="utf-8")
    (root / "scripts" / "gate.py").write_text("print('gate')\n", encoding="utf-8")


def write_subset(path: Path, rows) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False)
                              for row in rows) + "\n", encoding="utf-8")


class LoopTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.base = self.root / "base"
        make_skill(self.base)

        cases = {row["case_id"]: row
                 for row in load_jsonl(BENCH / "cases.jsonl")}
        truths = {row["case_id"]: row
                  for row in load_jsonl(BENCH / "ground_truth.jsonl")}
        self.cases_path = self.root / "cases.jsonl"
        self.truth_path = self.root / "ground_truth.jsonl"
        write_subset(self.cases_path, [cases[cid] for cid in CASE_IDS])
        write_subset(self.truth_path, [truths[cid] for cid in CASE_IDS])

        oracle = {item["case_id"]: item for item in build_oracle()}
        bad = {item["case_id"]: item for item in build_bad(build_oracle())}
        self.oracle = [oracle[cid] for cid in CASE_IDS]
        self.bad = [bad[cid] for cid in CASE_IDS]

        self.config = json.loads((REPO / "rsi" / "config.json").read_text(
            encoding="utf-8"))
        self.config["acceptance"]["seeds"] = 1
        self.config["acceptance"]["delta"] = 0.01
        self.config["acceptance"]["patience"] = 10
        self.config["budget"]["max_seconds"] = 60

        self.candidates = self.root / "candidates"
        self.candidates.mkdir()
        self.candidate_one = self._make_candidate("c1", "candidate one")
        self.candidate_two = self._make_candidate("c2", "candidate two")
        self.candidate_bad = self._make_candidate("frozen", "frozen edit")
        (self.candidate_bad / "bench" / "cases.jsonl").write_text(
            '{"tampered": true}\n', encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def _make_candidate(self, name: str, line: str) -> Path:
        path = self.candidates / name
        shutil.copytree(self.base, path)
        with (path / "SKILL.md").open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        return path

    def _inner_adapter(self):
        by_name = {
            "a000": self.bad,
            "a001": self.oracle,
            "a002": self.bad,
            "a003": self.bad,
        }

        def run(request):
            predictions = by_name.get(request.skill_root.name, self.oracle)
            return next(item for item in predictions
                        if item["case_id"] == request.case["case_id"])

        return runner.CallableAdapter(run)

    def _new_loop(self, run_name: str, proposals, steps=3, patience=10,
                  adapter=None):
        return loop.RsiLoop(
            base_skill=self.base,
            run_dir=self.root / run_name,
            inner_adapter=adapter or self._inner_adapter(),
            outer_agent=outer.FixtureOuter(proposals),
            cases_path=self.cases_path,
            truth_path=self.truth_path,
            bench_config_path=BENCH / "config.json",
            config=self.config,
            steps=steps,
            seeds=1,
            patience=patience,
        )

    def test_accepts_improvement_rejects_regression_and_frozen_edit(self):
        proposals = [
            {"candidate_dir": str(self.candidate_one), "rationale": "good"},
            {"candidate_dir": str(self.candidate_two), "rationale": "regression"},
            {"candidate_dir": str(self.candidate_bad), "rationale": "tamper"},
        ]
        summary = self._new_loop("run-main", proposals).run()

        archive = summary["archive"]
        self.assertEqual(len(archive), 4)  # baseline + 3 proposals
        self.assertLess(archive[0]["g"], 1.0)
        self.assertTrue(archive[1]["accepted"])
        self.assertAlmostEqual(archive[1]["g"], 1.0, places=4)
        self.assertFalse(archive[2]["accepted"])
        self.assertFalse(archive[3]["validation_ok"])
        self.assertTrue(any("冻结路径" in item
                            for item in archive[3]["violations"]))
        self.assertEqual(summary["accepted_count"], 1)
        self.assertEqual(summary["incumbent"]["agent_id"], "a001")
        self.assertEqual(summary["stop_reason"], "max_steps")

        trajectory = (self.root / "run-main" / "trajectory.jsonl").read_text(
            encoding="utf-8").strip().splitlines()
        self.assertEqual(len(trajectory), 4)
        for agent_id in ("a000", "a001", "a002", "a003"):
            self.assertTrue((self.root / "run-main" / "agents" / agent_id
                             / "SKILL.md").is_file())

    def test_stops_when_outer_exhausted(self):
        summary = self._new_loop("run-exhausted", [], steps=3).run()
        self.assertEqual(summary["steps_run"], 0)
        self.assertEqual(summary["stop_reason"], "outer_exhausted")

    def test_stops_on_patience(self):
        def always_bad(request):
            return next(item for item in self.bad
                        if item["case_id"] == request.case["case_id"])

        proposals = [
            {"candidate_dir": str(self.candidate_one), "rationale": "no gain"},
        ]
        summary = self._new_loop(
            "run-patience", proposals, steps=5, patience=1,
            adapter=runner.CallableAdapter(always_bad)).run()
        self.assertEqual(summary["stop_reason"], "patience")
        self.assertEqual(summary["steps_run"], 1)


if __name__ == "__main__":
    unittest.main()
