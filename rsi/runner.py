#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在固定预算下运行一个 math-solver 技能版本，并记录预测。

设计对应 plan.md §2.1 的内层循环：

    x_i = a(x_<i, r_pub_t(x_<i))       # 求解 + 自查
    x̂_t = 最终返回的 solution JSON
    b_t = 固定预算

Runner 只负责“执行 + 记录”，不做评分。评分在 grade.py 中复用
math-solver/bench/engine，避免 runner 与评分器互相耦合。

重要约束：
- solve 输出的结构门由 runner **重放**，tool_log 用真实退出码覆盖，
  不信任 adapter 自报的 tool_log。
- route / clarify 不附带 solution JSON。
- adapter 可以是夹具、Python 函数，或任意“stdin JSON → stdout JSON”的命令。

adapter 返回的预测格式：
    {"action": "solve", "output": {...}, "usage": {...}}
    {"action": "route", "route_to": "math-error-diagnosis", "reply": "..."}
    {"action": "clarify", "reply": "..."}
    None 表示该案例没有预测（用于夹具）。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SKILL = REPO_ROOT / "math-solver"
DEFAULT_CASES = DEFAULT_SKILL / "bench" / "cases.jsonl"
DEFAULT_VALIDATE = DEFAULT_SKILL / "scripts" / "validate_output.py"


class RunnerError(RuntimeError):
    """输入、adapter 或结构门无法执行。"""


# ---------------------------------------------------------------------------
# 技能版本与预算
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SkillBundle:
    """一个可被外层改写的技能版本。

    可编辑面与 plan.md §4.1 一致：SKILL.md 与 references/*.md。
    这里只负责读取与指纹；实际改写由 outer.py 完成。
    """

    root: Path

    def __post_init__(self):
        root = Path(self.root)
        if not (root / "SKILL.md").is_file():
            raise RunnerError(f"技能目录缺少 SKILL.md：{root}")

    def files(self) -> tuple[Path, ...]:
        root = Path(self.root)
        found = [root / "SKILL.md"]
        references = root / "references"
        if references.is_dir():
            found.extend(sorted(references.glob("*.md")))
        return tuple(found)

    def text(self) -> str:
        chunks = []
        for path in self.files():
            rel = path.relative_to(Path(self.root)).as_posix()
            chunks.append(f"\n\n<!-- {rel} -->\n\n")
            chunks.append(path.read_text(encoding="utf-8"))
        return "".join(chunks)

    def fingerprint(self) -> str:
        digest = hashlib.sha256()
        root = Path(self.root)
        for path in self.files():
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
        return digest.hexdigest()


@dataclass(frozen=True)
class Budget:
    """单题预算，对应论文的 b_t。

    token 与工具调用由 adapter 自己执行；runner 记录实际用量并标记超预算。
    对 CommandAdapter，max_seconds 同时是子进程硬超时。
    """

    max_tokens: int = 60_000
    max_tool_calls: int = 20
    max_seconds: float = 600.0
    max_cost_usd: float | None = None

    def __post_init__(self):
        if self.max_tokens <= 0 or self.max_tool_calls < 0 or self.max_seconds <= 0:
            raise RunnerError("预算必须为正数（tool_calls 可以为 0）")

    def as_dict(self) -> dict[str, Any]:
        return {
            "max_tokens": self.max_tokens,
            "max_tool_calls": self.max_tool_calls,
            "max_seconds": self.max_seconds,
            "max_cost_usd": self.max_cost_usd,
        }


@dataclass(frozen=True)
class RunRequest:
    case: dict[str, Any]
    skill_root: Path
    skill_fingerprint: str
    skill_text: str
    budget: Budget

    def as_dict(self) -> dict[str, Any]:
        return {
            "case": self.case,
            "skill_root": str(self.skill_root),
            "skill_fingerprint": self.skill_fingerprint,
            "skill_text": self.skill_text,
            "budget": self.budget.as_dict(),
        }


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class Adapter(Protocol):
    name: str

    def run(self, request: RunRequest) -> dict[str, Any] | None:
        ...


class FixtureAdapter:
    """回放已保存的预测，用于管线测试与夹具。"""

    def __init__(self, predictions: list[dict[str, Any]], name: str = "fixture"):
        self.name = name
        self._by_id = {item["case_id"]: item for item in predictions if "case_id" in item}

    def run(self, request: RunRequest) -> dict[str, Any] | None:
        item = self._by_id.get(request.case["case_id"])
        return copy.deepcopy(item) if item is not None else None


class CallableAdapter:
    """把一个 Python 函数包装成 adapter。"""

    def __init__(self, fn: Callable[[RunRequest], dict[str, Any] | None],
                 name: str = "callable"):
        self.name = name
        self._fn = fn

    def run(self, request: RunRequest) -> dict[str, Any] | None:
        return self._fn(request)


class CommandAdapter:
    """通过子进程调用外部智能体。

    协议：stdin 收一个 JSON 请求，stdout 返回一个 JSON 预测。
    命令用 JSON 数组给出，例如：
        --command '["python", "my_adapter.py"]'
    不经过 shell，避免引号与注入问题。
    """

    def __init__(self, argv: list[str], name: str = "command"):
        if not argv or not all(isinstance(item, str) for item in argv):
            raise RunnerError("command 必须是非空字符串数组")
        self.name = name
        self._argv = argv

    def run(self, request: RunRequest) -> dict[str, Any] | None:
        payload = json.dumps(request.as_dict(), ensure_ascii=False)
        try:
            result = subprocess.run(
                self._argv,
                input=payload,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=request.budget.max_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise RunnerError(
                f"adapter 超时（{request.budget.max_seconds}s）：{self._argv}"
            ) from exc
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise RunnerError(
                f"adapter 退出 {result.returncode}：{detail[:500]}"
            )
        if not result.stdout.strip():
            raise RunnerError("adapter 没有输出 JSON")
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RunnerError(f"adapter 输出不是合法 JSON：{exc}") from exc


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

class Runner:
    def __init__(self, skill: SkillBundle, adapter: Adapter, budget: Budget,
                 validate_script: Path | None = None,
                 python: str | None = None):
        self.skill = skill
        self.adapter = adapter
        self.budget = budget
        self.validate_script = Path(validate_script or DEFAULT_VALIDATE)
        self.python = python or sys.executable
        if not self.validate_script.is_file():
            raise RunnerError(f"找不到结构门脚本：{self.validate_script}")

    def run_case(self, case: dict[str, Any]) -> dict[str, Any] | None:
        request = RunRequest(
            case=case,
            skill_root=Path(self.skill.root).resolve(),
            skill_fingerprint=self.skill.fingerprint(),
            skill_text=self.skill.text(),
            budget=self.budget,
        )
        started = time.perf_counter()
        raw = self.adapter.run(request)
        elapsed = time.perf_counter() - started

        if raw is None:
            return None
        if not isinstance(raw, dict):
            raise RunnerError(
                f"{case.get('case_id')}：adapter 返回值必须是 JSON 对象或 null"
            )

        action = raw.get("action")
        record: dict[str, Any] = {"case_id": case["case_id"], "action": action}

        if action == "solve":
            output = raw.get("output")
            if isinstance(output, dict):
                record["output"] = output
                exit_code = self._run_validate(output)
                record["tool_log"] = [{
                    "command": (
                        "python3 scripts/validate_output.py validate "
                        f"--card {case['case_id']}.json --strict"
                    ),
                    "exit_code": exit_code,
                }]
            # 没有 output 时不伪造 tool_log；评分器会记 S_MISSING_OUTPUT。
        elif action in ("route", "clarify"):
            for key in ("route_to", "reply"):
                if key in raw:
                    record[key] = raw[key]
            if raw.get("output") is not None:
                record["runner_notes"] = ["dropped output for non-solve action"]
        else:
            # 未知 / 缺失 action：原样保留，交给评分器记 S_WRONG_ACTION。
            for key in ("route_to", "reply", "output"):
                if key in raw:
                    record[key] = raw[key]

        if raw.get("adapter_error"):
            record["adapter_error"] = str(raw["adapter_error"])
        if raw.get("raw_result"):
            record["raw_result"] = str(raw["raw_result"])[:3000]
        usage = raw.get("usage")
        record["usage"] = usage if isinstance(usage, dict) else {}
        record["elapsed_seconds"] = round(elapsed, 3)
        record["over_budget"] = self._over_budget(record, elapsed)
        return record

    def _run_validate(self, output: dict[str, Any]) -> int:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "output.json"
            path.write_text(json.dumps(output, ensure_ascii=False), encoding="utf-8")
            result = subprocess.run(
                [self.python, str(self.validate_script), "validate",
                 "--card", str(path), "--strict"],
                capture_output=True,
                encoding="utf-8",
                errors="replace",
            )
        return result.returncode

    def _over_budget(self, record: dict[str, Any], elapsed: float) -> bool:
        usage = record.get("usage") or {}
        tokens = usage.get("total_tokens")
        calls = usage.get("tool_calls")
        cost = usage.get("cost_usd")
        if isinstance(tokens, (int, float)) and tokens > self.budget.max_tokens:
            return True
        if isinstance(calls, (int, float)) and calls > self.budget.max_tool_calls:
            return True
        if isinstance(cost, (int, float)) and self.budget.max_cost_usd is not None:
            if cost > self.budget.max_cost_usd:
                return True
        return elapsed > self.budget.max_seconds


# ---------------------------------------------------------------------------
# 批量运行与 CLI
# ---------------------------------------------------------------------------

def load_cases(path: Path, split: str | None = None,
               case_ids: set[str] | None = None,
               limit: int | None = None) -> list[dict[str, Any]]:
    rows = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if split:
        rows = [row for row in rows if row.get("split") == split]
    if case_ids:
        rows = [row for row in rows if row["case_id"] in case_ids]
    if limit is not None:
        rows = rows[:limit]
    if not rows:
        raise RunnerError("筛选后没有案例")
    return rows


def run_cases(cases: list[dict[str, Any]], skill: SkillBundle, adapter: Adapter,
              budget: Budget, run_id: str, model: str | None = None,
              arm: str = "skill_gates") -> dict[str, Any]:
    runner = Runner(skill, adapter, budget)
    predictions = []
    for case in cases:
        record = runner.run_case(case)
        if record is not None:
            predictions.append(record)
    return {
        "arm": arm,
        "model": model or adapter.name,
        "run_id": run_id,
        "adapter": adapter.name,
        "skill_fingerprint": skill.fingerprint(),
        "budget": budget.as_dict(),
        "predictions": predictions,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="在固定预算下运行一个 math-solver 技能版本")
    parser.add_argument("--skill", default=str(DEFAULT_SKILL), help="技能目录")
    parser.add_argument("--cases", default=str(DEFAULT_CASES), help="cases.jsonl")
    parser.add_argument("--out", required=True, help="输出 predictions JSON")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--arm", default="skill_gates")
    parser.add_argument("--split", default=None, help="只跑某个 split")
    parser.add_argument("--case-ids", default=None, help="逗号分隔的 case_id")
    parser.add_argument("--limit", type=int, default=None)

    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--fixture", help="回放已保存的 predictions JSON")
    source.add_argument("--command", help='外部 adapter，JSON 数组，例如 \'["python","a.py"]\'')

    parser.add_argument("--max-tokens", type=int, default=Budget.max_tokens)
    parser.add_argument("--max-tool-calls", type=int, default=Budget.max_tool_calls)
    parser.add_argument("--max-seconds", type=float, default=Budget.max_seconds)
    parser.add_argument("--max-cost-usd", type=float, default=None)
    args = parser.parse_args(argv)

    case_ids = None
    if args.case_ids:
        case_ids = {item.strip() for item in args.case_ids.split(",") if item.strip()}

    try:
        cases = load_cases(Path(args.cases), args.split, case_ids, args.limit)
        skill = SkillBundle(Path(args.skill))
        budget = Budget(
            max_tokens=args.max_tokens,
            max_tool_calls=args.max_tool_calls,
            max_seconds=args.max_seconds,
            max_cost_usd=args.max_cost_usd,
        )
        if args.fixture:
            payload = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
            adapter: Adapter = FixtureAdapter(payload.get("predictions") or [])
        else:
            argv_list = json.loads(args.command)
            if not isinstance(argv_list, list):
                raise RunnerError("--command 必须是 JSON 数组")
            adapter = CommandAdapter(argv_list)

        run_id = args.run_id or time.strftime("run-%Y%m%d-%H%M%S")
        result = run_cases(cases, skill, adapter, budget, run_id,
                           model=args.model, arm=args.arm)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")

    print(json.dumps({
        "out": str(out),
        "case_count": len(cases),
        "prediction_count": len(result["predictions"]),
        "over_budget_count": sum(1 for item in result["predictions"]
                                 if item.get("over_budget")),
        "skill_fingerprint": result["skill_fingerprint"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
