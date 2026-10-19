#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验外层智能体提出的一版技能改写。

对应 plan.md §4：

- 只允许改 `SKILL.md` 与 `references/*.md`；
- `bench/`、`scripts/`、`tests/`、`example/` 冻结；
- 单次改动不超过 N 行（默认 40）；
- 不允许删除文件，不允许二进制文件，不允许符号链接。

用法：

    python rsi/validate_diff.py --base math-solver \
        --candidate runs/a001/math-solver

退出码：0 = 合法；1 = 有违规；2 = 输入非法。
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

DEFAULT_MAX_LINES = 40
FROZEN_DIRS = {"bench", "scripts", "tests", "example"}
IGNORED_PARTS = {"__pycache__", ".git"}
BINARY_SUFFIXES = {".pyc", ".pyo", ".png", ".jpg", ".jpeg", ".gif", ".pdf",
                   ".zip", ".tar", ".gz", ".so", ".dll", ".exe"}


class DiffError(RuntimeError):
    """输入无法读取。"""


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _files(root: Path) -> dict[str, Path]:
    found = {}
    for path in root.rglob("*"):
        if any(part in IGNORED_PARTS for part in path.parts):
            continue
        if path.is_symlink():
            found[_relative(path, root)] = path
            continue
        if path.is_file():
            found[_relative(path, root)] = path
    return found


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_editable(rel: str) -> bool:
    if rel == "SKILL.md":
        return True
    parts = rel.split("/")
    return (len(parts) == 2 and parts[0] == "references"
            and parts[1].endswith(".md"))


def _is_frozen(rel: str) -> bool:
    return rel.split("/", 1)[0] in FROZEN_DIRS


def _read_text(path: Path) -> str:
    if path.suffix.lower() in BINARY_SUFFIXES:
        raise DiffError(f"不允许二进制文件：{path.name}")
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise DiffError(f"文件不是 UTF-8 文本：{path.name}") from exc


def _changed_lines(base: Path | None, candidate: Path | None) -> int:
    if base is None:
        return len(_read_text(candidate).splitlines())
    if candidate is None:
        return len(_read_text(base).splitlines())
    old = _read_text(base).splitlines()
    new = _read_text(candidate).splitlines()
    count = 0
    for line in difflib.unified_diff(old, new, lineterm="", n=0):
        if line.startswith(("+++", "---", "@@")):
            continue
        if line.startswith(("+", "-")):
            count += 1
    return count


def validate_candidate(base: Path | str, candidate: Path | str,
                       max_changed_lines: int = DEFAULT_MAX_LINES) -> dict[str, Any]:
    base = Path(base)
    candidate = Path(candidate)
    if not base.is_dir():
        raise DiffError(f"base 不是目录：{base}")
    if not candidate.is_dir():
        raise DiffError(f"candidate 不是目录：{candidate}")
    if not (candidate / "SKILL.md").is_file():
        raise DiffError(f"candidate 缺少 SKILL.md：{candidate}")

    base_files = _files(base)
    candidate_files = _files(candidate)
    violations: list[str] = []
    changed: list[dict[str, Any]] = []
    total_lines = 0

    for rel in sorted(set(base_files) | set(candidate_files)):
        old = base_files.get(rel)
        new = candidate_files.get(rel)

        if old is not None and old.is_symlink():
            violations.append(f"base 含符号链接：{rel}")
            continue
        if new is not None and new.is_symlink():
            violations.append(f"candidate 含符号链接：{rel}")
            continue

        if old is None:
            status = "added"
        elif new is None:
            status = "deleted"
        elif _digest(old) != _digest(new):
            status = "modified"
        else:
            continue

        changed.append({"path": rel, "status": status})

        if _is_frozen(rel):
            violations.append(f"冻结路径被修改：{rel} ({status})")
        elif not _is_editable(rel):
            violations.append(f"不在可编辑面内：{rel} ({status})")
        elif status == "deleted":
            violations.append(f"不允许删除文件：{rel}")
        else:
            try:
                total_lines += _changed_lines(old, new)
            except DiffError as exc:
                violations.append(str(exc))

    if total_lines > max_changed_lines:
        violations.append(
            f"改动 {total_lines} 行，超过上限 {max_changed_lines} 行")

    return {
        "ok": not violations,
        "base": str(base),
        "candidate": str(candidate),
        "changed_files": changed,
        "changed_lines": total_lines,
        "max_changed_lines": max_changed_lines,
        "violations": violations,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验 math-solver 技能改写")
    parser.add_argument("--base", required=True, help="incumbent 技能目录")
    parser.add_argument("--candidate", required=True, help="候选技能目录")
    parser.add_argument("--max-lines", type=int, default=DEFAULT_MAX_LINES)
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args(argv)

    try:
        result = validate_candidate(args.base, args.candidate, args.max_lines)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    if args.json_out:
        path = Path(args.json_out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")

    print(json.dumps({
        "ok": result["ok"],
        "changed_files": result["changed_files"],
        "changed_lines": result["changed_lines"],
        "violations": result["violations"],
    }, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
