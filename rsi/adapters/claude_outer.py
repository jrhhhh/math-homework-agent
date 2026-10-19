#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""外层 adapter：用本机 `claude -p` 提出一版技能改写。

stdin 收 loop.py 的 OuterRequest JSON，stdout 返回：

    {"candidate_dir": "...", "rationale": "...", "expected_effect": "..."}

模型返回的是结构化 edits（find/replace），adapter 自己把 incumbent 复制到
run_dir/candidates/aNNN 并应用。模型侧没有工具，也不直接写文件。

环境变量：
- CLAUDE_BIN
- CLAUDE_OUTER_MODEL
- CLAUDE_OUTER_MAX_BUDGET_USD（默认 1.00）
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:  # 作为包导入
    from ._claude import (  # noqa: E402
        ClaudeError, budget_usd, extract_edits_object, run_claude,
        timeout_seconds, usage_from_payload,
    )
except ImportError:  # 作为脚本运行
    from _claude import (  # noqa: E402
        ClaudeError, budget_usd, extract_edits_object, run_claude,
        timeout_seconds, usage_from_payload,
    )

SYSTEM_PROMPT = """你是递归自我改进循环的外层智能体。
你的任务是根据失败摘要改写一个高中数学求解技能。你看不到标准答案。
只输出一个 JSON 对象，并用 <<<EDITS 和 EDITS>>> 包裹。
不要 Markdown 围栏，不要在包裹外写任何内容。"""

ALLOWED_TOP = "SKILL.md"
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".git")


def skill_text(root: Path) -> str:
    files = [root / "SKILL.md"]
    references = root / "references"
    if references.is_dir():
        files.extend(sorted(references.glob("*.md")))
    chunks = []
    for path in files:
        if path.is_file():
            chunks.append(f"\n\n<!-- {path.relative_to(root).as_posix()} -->\n\n")
            chunks.append(path.read_text(encoding="utf-8"))
    return "".join(chunks)


def _relative_allowed(rel: str) -> bool:
    if rel == ALLOWED_TOP:
        return True
    parts = rel.split("/")
    return (len(parts) == 2 and parts[0] == "references"
            and parts[1].endswith(".md"))


def _compact_history(history: list[dict], limit: int = 10) -> list[dict]:
    keys = ("step", "agent_id", "g", "severe_count_max", "accepted",
            "validation_ok", "changed_lines", "rationale", "violations", "error")
    return [{key: item.get(key) for key in keys} for item in history[-limit:]]


def build_prompt(request: dict) -> str:
    incumbent = request.get("incumbent") or {}
    incumbent_path = Path(incumbent.get("path") or "")
    text = skill_text(incumbent_path) if incumbent_path.is_dir() else ""
    history = _compact_history(request.get("history") or [])
    failures = (request.get("failure_summary") or [])[:30]
    return (
        "## 当前技能全文\n\n"
        f"{text}\n\n"
        "## Incumbent\n\n"
        f"g={incumbent.get('g')}  severe={incumbent.get('severe_count_max')}  "
        f"changed_lines={incumbent.get('changed_lines')}\n\n"
        "## 最近历史\n\n"
        f"{json.dumps(history, ensure_ascii=False, indent=2)}\n\n"
        "## 脱敏失败摘要（没有标准答案）\n\n"
        f"{json.dumps(failures, ensure_ascii=False, indent=2)}\n\n"
        "## 约束\n\n"
        f"- 只能修改 SKILL.md 或 references/*.md。\n"
        f"- 总改动不超过 {request.get('max_changed_lines', 40)} 行；只提一个聚焦的改动。\n"
        "- 不得修改输出契约、不得新增工具/网络/外部数据、不得声称不可用的工具。\n"
        "- 不得修改 bench/、scripts/、tests/、example/。\n\n"
        "## 输出格式（只输出一个 JSON 对象，放在 <<<EDITS 与 EDITS>>> 之间）\n\n"
        "<<<EDITS\n"
        "{\n"
        '  "rationale": "为什么这样改",\n'
        '  "expected_effect": "预期改善哪个失败项",\n'
        '  "edits": [\n'
        '    {"path": "SKILL.md", "find": "原文中一段精确文本",'
        ' "replace": "替换后的文本"}\n'
        "  ]\n"
        "}\n"
        "EDITS>>>\n"
        "find 必须在文件中逐字出现；replace 可以为空字符串（删除该段）。"
    )


def apply_edits(candidate: Path, edits: list[dict]) -> tuple[list[str], list[str]]:
    applied: list[str] = []
    errors: list[str] = []
    for index, edit in enumerate(edits[:5]):
        if not isinstance(edit, dict):
            errors.append(f"edit[{index}] 不是对象")
            continue
        rel = str(edit.get("path") or "").replace("\\", "/")
        if not _relative_allowed(rel):
            errors.append(f"edit[{index}] 路径不在可编辑面：{rel}")
            continue
        target = candidate / rel
        if not target.is_file():
            errors.append(f"edit[{index}] 文件不存在：{rel}")
            continue
        text = target.read_text(encoding="utf-8")
        find = edit.get("find")
        replace = edit.get("replace")
        if isinstance(find, str) and find and isinstance(replace, str):
            if find not in text:
                errors.append(f"edit[{index}] find 未命中：{rel}")
                continue
            target.write_text(text.replace(find, replace, 1), encoding="utf-8")
            applied.append(f"{rel}: replace")
        elif isinstance(edit.get("content"), str):
            target.write_text(edit["content"], encoding="utf-8")
            applied.append(f"{rel}: rewrite")
        else:
            errors.append(f"edit[{index}] 缺少 find/replace 或 content")
    return applied, errors


def main() -> int:
    try:
        raw = sys.stdin.buffer.read().decode("utf-8")
        request = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": f"无法读取 stdin JSON：{exc}"},
                         ensure_ascii=False))
        return 2

    incumbent = request.get("incumbent") or {}
    incumbent_path = Path(incumbent.get("path") or "")
    candidate = Path(request.get("candidate_dir") or "")
    run_dir = Path(request.get("run_dir") or "")

    if not incumbent_path.is_dir():
        print(json.dumps({"error": f"incumbent 不存在：{incumbent_path}"},
                         ensure_ascii=False))
        return 2
    if not candidate or not run_dir:
        print(json.dumps({"error": "缺少 candidate_dir 或 run_dir"},
                         ensure_ascii=False))
        return 2
    # 只允许在 run_dir 下创建候选，避免任意路径写入。
    try:
        candidate.resolve().relative_to(run_dir.resolve())
    except ValueError:
        print(json.dumps({"error": "candidate_dir 必须在 run_dir 下"},
                         ensure_ascii=False))
        return 2

    if candidate.exists():
        shutil.rmtree(candidate)
    candidate.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(incumbent_path, candidate, ignore=IGNORE)

    try:
        with tempfile.TemporaryDirectory() as directory:
            system_path = Path(directory) / "system.txt"
            system_path.write_text(
                SYSTEM_PROMPT + "\n\n" + build_prompt(request),
                encoding="utf-8")
            payload = run_claude(
                "请按系统提示返回一个改写 JSON。",
                system_prompt_file=str(system_path),
                max_budget_usd=budget_usd(
                    request, 1.00, "CLAUDE_OUTER_MAX_BUDGET_USD"),
                timeout=timeout_seconds(request),
                model=os.environ.get("CLAUDE_OUTER_MODEL")
                or os.environ.get("CLAUDE_MODEL"),
                cwd=str(run_dir),
            )
    except ClaudeError as exc:
        print(json.dumps({
            "candidate_dir": str(candidate),
            "rationale": f"[outer error] {exc}",
            "expected_effect": "",
            "usage": {},
        }, ensure_ascii=False))
        return 0

    usage = usage_from_payload(payload)
    parsed = extract_edits_object(payload.get("result") or "")
    rationale = ""
    expected_effect = ""
    edits: list[dict] = []
    errors: list[str] = []
    if parsed is None:
        errors.append("无法从模型输出解析 edits JSON")
    else:
        rationale = str(parsed.get("rationale") or "")
        expected_effect = str(parsed.get("expected_effect") or "")
        raw_edits = parsed.get("edits")
        if isinstance(raw_edits, list):
            edits = raw_edits
        else:
            errors.append("输出缺少 edits 数组")

    applied, apply_errors = apply_edits(candidate, edits)
    errors.extend(apply_errors)
    if errors:
        rationale = (rationale + "\n[adapter errors] " + "; ".join(errors)).strip()

    print(json.dumps({
        "candidate_dir": str(candidate),
        "rationale": rationale,
        "expected_effect": expected_effect,
        "applied_edits": applied,
        "adapter_errors": errors,
        "raw_result": (payload.get("result") or "")[:3000] if parsed is None else None,
        "usage": usage,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
