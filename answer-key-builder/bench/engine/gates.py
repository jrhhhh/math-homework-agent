# -*- coding: utf-8 -*-
"""结构门重放与 tool_log 核对。"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

BENCH = Path(__file__).resolve().parents[1]
SKILL = BENCH.parent
VALIDATE = SKILL / "scripts" / "validate_output.py"


def run_validate(output):
    """把输出写成临时 JSON，跑技能结构门；返回 (exit_code, payload)。"""
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "output.json"
        path.write_text(json.dumps(output, ensure_ascii=False), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(VALIDATE), "validate", "--card", str(path), "--strict"],
            capture_output=True, encoding="utf-8", errors="replace",
        )
        payload = {}
        if result.stdout:
            try:
                payload = json.loads(result.stdout)
            except json.JSONDecodeError:
                payload = {"raw": result.stdout}
        return result.returncode, payload


def _validate_entries(prediction):
    entries = prediction.get("tool_log") or []
    return [entry for entry in entries
            if isinstance(entry, dict)
            and "validate_output" in str(entry.get("command", ""))
            and "validate" in str(entry.get("command", ""))]


def check_tool_log(prediction, output, actual_exit, arm, config):
    """返回 (present, fidelity, severe_code, detail)。"""
    entries = _validate_entries(prediction)
    required = arm in set(config.get("require_tool_log_arms", []))

    if not entries:
        if required:
            return False, False, "S_MISSING_TOOL_LOG", "skill_gates 组缺少 validate 记录"
        return None, None, None, "未记录 tool_log（非必需组）"

    if not any("--strict" in str(entry.get("command", "")) for entry in entries):
        return True, False, "S_TOOL_LOG_MISMATCH", "validate 命令缺少 --strict"

    claimed = [entry.get("exit_code") for entry in entries]
    if any(value != actual_exit for value in claimed):
        return True, False, "S_TOOL_LOG_MISMATCH", f"声称 {claimed}，实测 {actual_exit}"
    return True, True, None, f"声称与实测一致（exit {actual_exit}）"
