#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""外层智能体接口。

对应 plan.md §2.3：

    a_k = a_out(a_<k, g(a_<k))

外层只拿到：
- 当前 incumbent 的路径、g、严重失败数；
- 历史候选与接受/拒绝记录；
- 脱敏失败摘要（案例 ID、子集、失败检查项、严重码）；
- 选拔题的**输入**路径（cases.jsonl，不含标准答案）；
- 预算、可编辑面、单次 diff 行数上限。

外层返回一个**完整的候选技能目录**，而不是直接修改 incumbent。
真正的路径/行数/冻结校验由 loop.py 调用 validate_diff.py 完成。
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol


class OuterError(RuntimeError):
    """外层智能体输入/输出非法。"""


@dataclass(frozen=True)
class CandidateProposal:
    candidate_dir: Path
    rationale: str = ""
    expected_effect: str = ""
    usage: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_dir": str(self.candidate_dir),
            "rationale": self.rationale,
            "expected_effect": self.expected_effect,
            "usage": self.usage,
        }


class OuterAgent(Protocol):
    name: str

    def propose(self, request: dict[str, Any]) -> CandidateProposal | None:
        ...


def _coerce(raw: dict[str, Any] | None) -> CandidateProposal | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise OuterError("外层返回值必须是 JSON 对象或 null")
    candidate_dir = raw.get("candidate_dir")
    if not candidate_dir:
        raise OuterError("外层返回值缺少 candidate_dir")
    usage = raw.get("usage")
    return CandidateProposal(
        candidate_dir=Path(candidate_dir),
        rationale=str(raw.get("rationale") or ""),
        expected_effect=str(raw.get("expected_effect") or ""),
        usage=usage if isinstance(usage, dict) else {},
    )


class FixtureOuter:
    """按顺序回放候选目录，用于管线与算法测试。"""

    def __init__(self, proposals: list[dict[str, Any] | CandidateProposal],
                 name: str = "fixture-outer"):
        self.name = name
        self._proposals = [
            item if isinstance(item, CandidateProposal) else _coerce(item)
            for item in proposals
        ]
        self._index = 0

    def propose(self, request: dict[str, Any]) -> CandidateProposal | None:
        if self._index >= len(self._proposals):
            return None
        proposal = self._proposals[self._index]
        self._index += 1
        return proposal


class CallableOuter:
    def __init__(self, fn: Callable[[dict[str, Any]], dict[str, Any] | None],
                 name: str = "callable-outer"):
        self.name = name
        self._fn = fn

    def propose(self, request: dict[str, Any]) -> CandidateProposal | None:
        return _coerce(self._fn(request))


class CommandOuter:
    """stdin JSON 请求 → stdout JSON 候选。

    返回格式：
        {"candidate_dir": "...", "rationale": "...", "expected_effect": "..."}
    或 null（停止）。
    """

    def __init__(self, argv: list[str], name: str = "command-outer",
                 timeout: float = 600.0):
        if not argv or not all(isinstance(item, str) for item in argv):
            raise OuterError("command 必须是非空字符串数组")
        self.name = name
        self._argv = argv
        self._timeout = timeout

    def propose(self, request: dict[str, Any]) -> CandidateProposal | None:
        try:
            result = subprocess.run(
                self._argv,
                input=json.dumps(request, ensure_ascii=False),
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=self._timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise OuterError(f"外层 adapter 超时（{self._timeout}s）") from exc
        if result.returncode != 0:
            raise OuterError(
                f"外层 adapter 退出 {result.returncode}：{result.stderr.strip()[:500]}")
        if not result.stdout.strip():
            raise OuterError("外层 adapter 没有输出 JSON")
        try:
            raw = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise OuterError(f"外层 adapter 输出不是合法 JSON：{exc}") from exc
        return _coerce(raw)


def main(argv: list[str] | None = None) -> int:
    """供调试：把一份 request JSON 发给命令，打印候选。"""
    import argparse

    parser = argparse.ArgumentParser(description="调试外层智能体命令")
    parser.add_argument("--command", required=True,
                        help='JSON 数组，例如 \'["python","outer.py"]\'')
    parser.add_argument("--request", required=True, help="request JSON 文件")
    args = parser.parse_args(argv)
    try:
        request = json.loads(Path(args.request).read_text(encoding="utf-8"))
        agent = CommandOuter(json.loads(args.command))
        proposal = agent.propose(request)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(proposal.as_dict() if proposal else None,
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
