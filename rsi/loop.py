#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""递归自我改进循环（算法 1）。

对应 plan.md §2.3 / §2.4：

    Grade(a) = 在选拔集上跑 R 个种子，返回 g(a)
    g(a0) <- Grade(a0)
    for k = 1..K-1:
        a_k <- a_out(a_<k, g(a_<k))       # 外层提出完整候选目录
        g(a_k) <- Grade(a_k)
    a* <- argmax_{a in a_<=K} g(a)

接受规则（预注册，见 rsi/config.json）：
- g 提升超过 delta；
- 严重失败数不增加；
- 没有超预算；
- 通过 validate_diff（可编辑面、冻结路径、行数上限）。

所有被评分的候选都进归档；incumbent 是“合格候选中学分最高者”，
不是“最后一次被接受的候选”。
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from rsi import grade, outer, runner, validate_diff  # noqa: E402

BENCH = REPO_ROOT / "math-solver" / "bench"
DEFAULT_SKILL = REPO_ROOT / "math-solver"
DEFAULT_CONFIG = REPO_ROOT / "rsi" / "config.json"


class LoopError(RuntimeError):
    """循环无法继续。"""


@dataclass
class AgentRecord:
    step: int
    agent_id: str
    path: Path
    g: float | None = None
    severe_count_max: int | None = None
    over_budget_count: int = 0
    accepted: bool = False
    validation_ok: bool = False
    violations: list[str] = field(default_factory=list)
    rationale: str = ""
    expected_effect: str = ""
    changed_files: list[dict[str, Any]] = field(default_factory=list)
    changed_lines: int = 0
    failure_summary: list[dict[str, Any]] = field(default_factory=list)
    inner_cost_usd: float = 0.0
    inner_tokens: int = 0
    outer_usage: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "agent_id": self.agent_id,
            "path": str(self.path),
            "g": self.g,
            "severe_count_max": self.severe_count_max,
            "over_budget_count": self.over_budget_count,
            "accepted": self.accepted,
            "validation_ok": self.validation_ok,
            "violations": self.violations,
            "rationale": self.rationale,
            "expected_effect": self.expected_effect,
            "changed_files": self.changed_files,
            "changed_lines": self.changed_lines,
            "failure_summary": self.failure_summary,
            "inner_cost_usd": self.inner_cost_usd,
            "inner_tokens": self.inner_tokens,
            "outer_usage": self.outer_usage,
            "error": self.error,
        }


def copy_skill(source: Path, destination: Path) -> None:
    if destination.exists():
        raise LoopError(f"目标快照已存在：{destination}")
    shutil.copytree(
        source, destination,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".git"),
    )


def load_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


class RsiLoop:
    def __init__(self, base_skill: Path, run_dir: Path,
                 inner_adapter: runner.Adapter, outer_agent: outer.OuterAgent,
                 cases_path: Path, truth_path: Path, bench_config_path: Path,
                 config: dict[str, Any],
                 steps: int | None = None, seeds: int | None = None,
                 delta: float | None = None, patience: int | None = None,
                 max_changed_lines: int = validate_diff.DEFAULT_MAX_LINES,
                 run_id: str | None = None):
        self.base_skill = Path(base_skill)
        self.run_dir = Path(run_dir)
        self.inner_adapter = inner_adapter
        self.outer_agent = outer_agent
        self.cases_path = Path(cases_path)
        self.truth_path = Path(truth_path)
        self.bench_config_path = Path(bench_config_path)
        self.config = config

        acceptance = config.get("acceptance") or {}
        self.steps = int(steps if steps is not None
                         else acceptance.get("trajectory_length", 20))
        self.seeds = int(seeds if seeds is not None
                         else acceptance.get("seeds", 2))
        self.delta = float(delta if delta is not None
                           else acceptance.get("delta", 0.01))
        self.patience = int(patience if patience is not None
                            else acceptance.get("patience", 10))
        self.reject_on_severe_increase = bool(
            acceptance.get("reject_on_severe_increase", True))
        self.max_changed_lines = int(max_changed_lines)
        self.budget = runner.Budget(**(config.get("budget") or {}))
        self.editable = list(config.get("editable") or [])
        self.frozen = list(config.get("frozen") or [])
        self.run_id = run_id or time.strftime("rsi-%Y%m%d-%H%M%S")

        if self.steps < 0:
            raise LoopError("steps 不能为负")
        if self.seeds < 1:
            raise LoopError("seeds 至少为 1")

    # -- 评分 ---------------------------------------------------------------
    def grade_skill(self, skill_dir: Path, agent_id: str) -> dict[str, Any]:
        payloads = []
        for seed in range(self.seeds):
            result = runner.run_cases(
                cases=runner.load_cases(self.cases_path),
                skill=runner.SkillBundle(skill_dir),
                adapter=self.inner_adapter,
                budget=self.budget,
                run_id=f"{self.run_id}-{agent_id}-s{seed}",
                model=None,
                arm="skill_gates",
            )
            payloads.append(result)
        return grade.grade_payloads(
            payloads, self.cases_path, self.truth_path, self.bench_config_path)

    # -- 外层请求 -----------------------------------------------------------
    def _outer_request(self, step: int,
                       incumbent: AgentRecord,
                       archive: list[AgentRecord]) -> dict[str, Any]:
        return {
            "step": step,
            "run_id": self.run_id,
            "run_dir": str(self.run_dir),
            "candidate_dir": str(self.run_dir / "candidates" / f"a{step:03d}"),
            "incumbent": incumbent.as_dict(),
            "history": [record.as_dict() for record in archive],
            "failure_summary": incumbent.failure_summary,
            "cases_path": str(self.cases_path),
            "budget": self.budget.as_dict(),
            "max_changed_lines": self.max_changed_lines,
            "editable": self.editable,
            "frozen": self.frozen,
            "delta": self.delta,
        }

    # -- 循环 ---------------------------------------------------------------
    def run(self) -> dict[str, Any]:
        if self.run_dir.exists() and any(self.run_dir.iterdir()):
            raise LoopError(f"run_dir 非空：{self.run_dir}")
        agents_dir = self.run_dir / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        (self.run_dir / "candidates").mkdir(parents=True, exist_ok=True)

        base_snapshot = agents_dir / "a000"
        copy_skill(self.base_skill, base_snapshot)
        base_grade = self.grade_skill(base_snapshot, "a000")
        baseline = AgentRecord(
            step=0, agent_id="a000", path=base_snapshot,
            g=base_grade["g"],
            severe_count_max=base_grade["severe_count_max"],
            over_budget_count=base_grade["over_budget_count_total"],
            accepted=False,
            validation_ok=True,
            rationale="baseline",
            failure_summary=base_grade["failure_summary"],
            inner_cost_usd=base_grade["cost_usd_total"],
            inner_tokens=base_grade["tokens_total"],
        )
        archive = [baseline]
        incumbent = baseline
        accepted_count = 0
        since_improvement = 0
        stop_reason = "max_steps"

        trajectory_path = self.run_dir / "trajectory.jsonl"
        self._append(trajectory_path, baseline)

        for step in range(1, self.steps + 1):
            request = self._outer_request(step, incumbent, archive)
            try:
                proposal = self.outer_agent.propose(request)
            except Exception as exc:  # noqa: BLE001
                stop_reason = f"outer_error: {exc}"
                break
            if proposal is None:
                stop_reason = "outer_exhausted"
                break

            agent_id = f"a{step:03d}"
            snapshot = agents_dir / agent_id
            record = AgentRecord(
                step=step, agent_id=agent_id, path=snapshot,
                rationale=proposal.rationale,
                expected_effect=proposal.expected_effect,
                outer_usage=proposal.usage,
            )

            try:
                copy_skill(proposal.candidate_dir, snapshot)
            except Exception as exc:  # noqa: BLE001
                record.error = f"无法创建候选快照：{exc}"
                record.violations = [record.error]
                archive.append(record)
                self._append(trajectory_path, record)
                since_improvement += 1
                continue

            try:
                validation = validate_diff.validate_candidate(
                    incumbent.path, snapshot, self.max_changed_lines)
            except Exception as exc:  # noqa: BLE001
                record.error = f"diff 校验失败：{exc}"
                record.violations = [record.error]
                archive.append(record)
                self._append(trajectory_path, record)
                since_improvement += 1
                continue

            record.validation_ok = validation["ok"]
            record.violations = validation["violations"]
            record.changed_files = validation["changed_files"]
            record.changed_lines = validation["changed_lines"]

            if not validation["ok"]:
                archive.append(record)
                self._append(trajectory_path, record)
                since_improvement += 1
                continue
            if not validation["changed_files"]:
                record.violations = ["候选与 incumbent 完全相同"]
                archive.append(record)
                self._append(trajectory_path, record)
                since_improvement += 1
                continue

            try:
                candidate_grade = self.grade_skill(snapshot, agent_id)
            except Exception as exc:  # noqa: BLE001
                record.error = f"评分失败：{exc}"
                archive.append(record)
                self._append(trajectory_path, record)
                since_improvement += 1
                continue

            record.g = candidate_grade["g"]
            record.severe_count_max = candidate_grade["severe_count_max"]
            record.over_budget_count = candidate_grade["over_budget_count_total"]
            record.failure_summary = candidate_grade["failure_summary"]
            record.inner_cost_usd = candidate_grade["cost_usd_total"]
            record.inner_tokens = candidate_grade["tokens_total"]

            improves = (
                incumbent.g is None
                or record.g > incumbent.g + self.delta
            )
            severe_ok = (
                not self.reject_on_severe_increase
                or incumbent.severe_count_max is None
                or record.severe_count_max <= incumbent.severe_count_max
            )
            budget_ok = record.over_budget_count == 0
            record.accepted = bool(improves and severe_ok and budget_ok)

            if record.accepted:
                accepted_count += 1
                since_improvement = 0
            else:
                since_improvement += 1

            archive.append(record)
            self._append(trajectory_path, record)

            # 与论文 eq. (4) 一致：incumbent 是合格候选中的 argmax。
            eligible = [
                item for item in archive
                if item.g is not None
                and item.over_budget_count == 0
                and (not self.reject_on_severe_increase
                     or item.severe_count_max is None
                     or item.severe_count_max <= incumbent.severe_count_max
                     or item is incumbent)
            ]
            best = max(eligible, key=lambda item: item.g)
            if best.g > incumbent.g:
                incumbent = best

            if since_improvement >= self.patience:
                stop_reason = "patience"
                break
        else:
            stop_reason = "max_steps"

        inner_cost = round(sum(record.inner_cost_usd for record in archive), 4)
        outer_cost = round(sum(float((record.outer_usage or {}).get("cost_usd") or 0)
                               for record in archive), 4)
        summary = {
            "run_id": self.run_id,
            "base_skill": str(self.base_skill),
            "steps_requested": self.steps,
            "steps_run": len(archive) - 1,
            "seeds": self.seeds,
            "delta": self.delta,
            "patience": self.patience,
            "accepted_count": accepted_count,
            "stop_reason": stop_reason,
            "inner_cost_usd_total": inner_cost,
            "outer_cost_usd_total": outer_cost,
            "total_cost_usd": round(inner_cost + outer_cost, 4),
            "incumbent": incumbent.as_dict(),
            "archive": [record.as_dict() for record in archive],
        }
        (self.run_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        return summary

    @staticmethod
    def _append(path: Path, record: AgentRecord) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.as_dict(), ensure_ascii=False) + "\n")


def _load_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="运行 math-solver 的 RSI 循环")
    parser.add_argument("--base-skill", default=str(DEFAULT_SKILL))
    parser.add_argument("--cases", default=str(BENCH / "cases.jsonl"))
    parser.add_argument("--ground-truth", default=str(BENCH / "ground_truth.jsonl"))
    parser.add_argument("--bench-config", default=str(BENCH / "config.json"))
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--steps", type=int, default=None)
    parser.add_argument("--seeds", type=int, default=None)
    parser.add_argument("--delta", type=float, default=None)
    parser.add_argument("--patience", type=int, default=None)
    parser.add_argument("--max-changed-lines", type=int,
                        default=validate_diff.DEFAULT_MAX_LINES)

    inner = parser.add_mutually_exclusive_group(required=True)
    inner.add_argument("--inner-fixture", help="所有候选都用同一份 predictions（冒烟用）")
    inner.add_argument("--inner-command", help='JSON 数组，例如 \'["python","inner.py"]\'')

    outer_group = parser.add_mutually_exclusive_group(required=True)
    outer_group.add_argument("--outer-fixture",
                             help='JSON：{"candidates":[{"candidate_dir":"..."}]}')
    outer_group.add_argument("--outer-command",
                             help='JSON 数组，例如 \'["python","outer.py"]\'')

    args = parser.parse_args(argv)

    try:
        config = load_config(Path(args.config))
        if args.inner_fixture:
            payload = _load_json(Path(args.inner_fixture))
            inner_adapter: runner.Adapter = runner.FixtureAdapter(
                payload.get("predictions") or [], name="inner-fixture")
        else:
            inner_adapter = runner.CommandAdapter(json.loads(args.inner_command))

        if args.outer_fixture:
            data = _load_json(Path(args.outer_fixture))
            candidates = data.get("candidates") if isinstance(data, dict) else data
            if not isinstance(candidates, list):
                raise LoopError("outer fixture 必须是数组或带 candidates 数组的对象")
            outer_agent: outer.OuterAgent = outer.FixtureOuter(candidates)
        else:
            outer_agent = outer.CommandOuter(json.loads(args.outer_command))

        loop = RsiLoop(
            base_skill=Path(args.base_skill),
            run_dir=Path(args.run_dir),
            inner_adapter=inner_adapter,
            outer_agent=outer_agent,
            cases_path=Path(args.cases),
            truth_path=Path(args.ground_truth),
            bench_config_path=Path(args.bench_config),
            config=config,
            steps=args.steps,
            seeds=args.seeds,
            delta=args.delta,
            patience=args.patience,
            max_changed_lines=args.max_changed_lines,
            run_id=args.run_id,
        )
        summary = loop.run()
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    print(json.dumps({
        "run_id": summary["run_id"],
        "steps_run": summary["steps_run"],
        "accepted_count": summary["accepted_count"],
        "stop_reason": summary["stop_reason"],
        "incumbent": {
            "agent_id": summary["incumbent"]["agent_id"],
            "g": summary["incumbent"]["g"],
            "severe_count_max": summary["incumbent"]["severe_count_max"],
        },
        "inner_cost_usd_total": summary["inner_cost_usd_total"],
        "outer_cost_usd_total": summary["outer_cost_usd_total"],
        "total_cost_usd": summary["total_cost_usd"],
        "run_dir": args.run_dir,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
