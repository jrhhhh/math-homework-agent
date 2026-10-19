#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""内层 adapter：用本机 `claude -p` 运行一个 math-solver 技能版本。

stdin 收 runner 的 RunRequest JSON，stdout 返回 bench 预测 JSON。

环境变量：
- CLAUDE_BIN：claude 可执行文件（默认 claude）
- CLAUDE_INNER_MODEL：内层模型（默认用 CLI 当前配置）
- CLAUDE_INNER_MAX_BUDGET_USD：单题美元上限（默认取 request.budget.max_cost_usd，
  没有则 0.50）

模型侧**不启用任何工具**；它不能执行 Python/SymPy，也不应声称执行过。
"""

from __future__ import annotations

import json
import os
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
        ClaudeError, budget_usd, prediction_from_text, run_claude,
        timeout_seconds, usage_from_payload,
    )
except ImportError:  # 作为脚本运行
    from _claude import (  # noqa: E402
        ClaudeError, budget_usd, prediction_from_text, run_claude,
        timeout_seconds, usage_from_payload,
    )

SYSTEM_PROMPT = """你正在以 math-solver 技能的身份接受评测。
严格遵循用户消息里的技能说明。你没有外部工具：不要声称运行过 Python、SymPy、
计算器或结构门。只输出一个 JSON 对象，并用 <<<PREDICTION 和 PREDICTION>>> 包裹。
不要 Markdown 围栏，不要在包裹外写任何内容。"""

OUTPUT_RULES = """## 输出要求
把下面这个 JSON 对象放在 <<<PREDICTION 与 PREDICTION>>> 之间：
- 求解任务：{"action":"solve","output":<技能要求的 solution JSON>}
- 转交任务：{"action":"route","route_to":"<技能名>","reply":"..."}
- 澄清任务：{"action":"clarify","reply":"..."}
格式示例：
<<<PREDICTION
{"action":"clarify","reply":"请补充条件"}
PREDICTION>>>
不要在包裹外输出任何内容。"""


def build_system_prompt(skill_text: str) -> str:
    return (
        f"{SYSTEM_PROMPT}\n\n"
        "## 技能说明\n\n"
        f"{skill_text}\n\n"
        f"{OUTPUT_RULES}\n"
    )


def build_user_prompt(case: dict) -> str:
    return (
        "## 本次案例\n\n"
        f"{json.dumps(case, ensure_ascii=False, indent=2)}\n\n"
        "请按系统提示输出包裹好的 JSON。\n"
    )


def main() -> int:
    try:
        raw = sys.stdin.buffer.read().decode("utf-8")
        request = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": f"无法读取 stdin JSON：{exc}"},
                         ensure_ascii=False))
        return 2

    case = request.get("case")
    skill_text = request.get("skill_text") or ""
    if not isinstance(case, dict) or not skill_text:
        print(json.dumps({"error": "request 缺少 case 或 skill_text"},
                         ensure_ascii=False))
        return 2

    try:
        with tempfile.TemporaryDirectory() as directory:
            system_path = Path(directory) / "system.txt"
            system_path.write_text(build_system_prompt(skill_text),
                                   encoding="utf-8")
            payload = run_claude(
                build_user_prompt(case),
                system_prompt_file=str(system_path),
                max_budget_usd=budget_usd(
                    request, 0.50, "CLAUDE_INNER_MAX_BUDGET_USD"),
                timeout=timeout_seconds(request),
                model=os.environ.get("CLAUDE_INNER_MODEL")
                or os.environ.get("CLAUDE_MODEL"),
                cwd=request.get("skill_root"),
            )
    except ClaudeError as exc:
        print(json.dumps({"action": None,
                          "adapter_error": str(exc),
                          "usage": {}}, ensure_ascii=False))
        return 0

    usage = usage_from_payload(payload)
    if payload.get("is_error"):
        print(json.dumps({
            "action": None,
            "adapter_error": "; ".join(payload.get("errors") or [])
            or payload.get("terminal_reason") or "CLI is_error",
            "usage": usage,
        }, ensure_ascii=False))
        return 0

    prediction = prediction_from_text(payload.get("result") or "")
    prediction["usage"] = usage
    print(json.dumps(prediction, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
